"""Deterministic workflow controller.

An explicit state machine drives the pipeline:

    UNDERSTAND -> PLAN -> CONSTRUCT -> VERIFY -> DONE
                            ^             |
                            +-- REPLAN <--+   (while violations remain and budget is left)

This is deliberately *not* an LLM agent: the dependency structure between the four agents is
known in advance, so a plain controller is easier to debug, test and evaluate.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from spatialmind.agents.construction import construct_scene
from spatialmind.agents.llm import LLMProvider
from spatialmind.agents.planner import plan, replan
from spatialmind.agents.understanding import UnderstandingAgent
from spatialmind.geometry.verifier import VerificationReport, verify
from spatialmind.memory import SpatialMemory
from spatialmind.schemas import SceneSpec


class Stage(str, Enum):
    UNDERSTAND = "understand"
    PLAN = "plan"
    INJECT_FAULT = "inject_fault"
    CONSTRUCT = "construct"
    VERIFY = "verify"
    REPLAN = "replan"
    DONE = "done"


class TraceStep(BaseModel):
    stage: Stage
    iteration: int
    duration_ms: float
    summary: str
    passed: bool | None = None


class GenerationResult(BaseModel):
    prompt: str
    provider: str
    spec: SceneSpec
    memory: dict[str, Any]
    scene: dict[str, Any]
    initial_report: VerificationReport
    final_report: VerificationReport
    iterations: int
    passed: bool
    refined: bool = Field(description="True if refinement fixed a layout that initially failed")
    fault_injected: str | None = None
    trace: list[TraceStep]
    total_ms: float


def inject_fault(memory: SpatialMemory) -> str | None:
    """Evaluation aid (proposal slide 11): deliberately corrupt a valid layout.

    Moves the last-placed object onto the first-placed object so verification has a known
    violation to detect and the refinement loop has something to repair. Deterministic.
    """
    placed = list(memory.objects.values())
    if len(placed) < 2:
        return None
    victim, anchor = placed[-1], placed[0]
    memory.objects[victim.id] = victim.model_copy(update={"x": anchor.x, "y": anchor.y})
    memory.log("fault", f"moved {victim.id} onto {anchor.id}")
    return f"{victim.id} moved onto {anchor.id}"


class _Tracer:
    """Collects one timed TraceStep per controller state."""

    def __init__(self) -> None:
        self.steps: list[TraceStep] = []
        self._t0 = time.perf_counter()

    def start(self) -> None:
        self._t0 = time.perf_counter()

    def record(
        self, stage: Stage, iteration: int, summary: str, passed: bool | None = None
    ) -> None:
        elapsed_ms = (time.perf_counter() - self._t0) * 1000
        self.steps.append(
            TraceStep(
                stage=stage,
                iteration=iteration,
                duration_ms=round(elapsed_ms, 2),
                summary=summary,
                passed=passed,
            )
        )


class Pipeline:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider
        self.agent = UnderstandingAgent(provider)

    def run(
        self,
        prompt: str,
        room_width: float | None = None,
        room_depth: float | None = None,
        max_iterations: int = 3,
        with_fault: bool = False,
    ) -> GenerationResult:
        started = time.perf_counter()
        tracer = _Tracer()

        # UNDERSTAND
        tracer.start()
        spec = self.agent.understand(prompt, room_width, room_depth)
        wanted = sum(o.quantity for o in spec.objects)
        tracer.record(
            Stage.UNDERSTAND,
            0,
            f"{spec.room_type.value}: {wanted} objects, {len(spec.constraints)} constraints",
        )

        # PLAN
        tracer.start()
        memory = plan(spec)
        tracer.record(Stage.PLAN, 0, f"placed {len(memory.objects)}/{wanted} objects")

        fault: str | None = None
        if with_fault:
            tracer.start()
            fault = inject_fault(memory)
            tracer.record(Stage.INJECT_FAULT, 0, fault or "not enough objects to inject a fault")

        # CONSTRUCT -> VERIFY -> (REPLAN)*
        initial: VerificationReport | None = None
        iteration = 0
        while True:
            tracer.start()
            scene = construct_scene(memory)
            tracer.record(
                Stage.CONSTRUCT, iteration, f"scene payload with {len(scene['objects'])} objects"
            )

            tracer.start()
            report = verify(memory)
            if initial is None:
                initial = report
            hard = sum(1 for v in report.violations if v.hard)
            verdict = (
                "all checks passed"
                if report.passed
                else f"{len(report.violations)} violations ({hard} geometric)"
            )
            tracer.record(Stage.VERIFY, iteration, verdict, passed=report.passed)

            if report.passed or iteration >= max_iterations:
                break

            tracer.start()
            flagged = report.violating_objects()
            replan(memory, report)
            iteration += 1
            tracer.record(
                Stage.REPLAN, iteration, f"re-placed {', '.join(flagged) or 'unplaced objects'}"
            )

        assert initial is not None  # the loop body always runs at least once
        tracer.start()
        tracer.record(
            Stage.DONE,
            iteration,
            "validated scene" if report.passed else "stopped with remaining violations",
            passed=report.passed,
        )
        return GenerationResult(
            prompt=prompt,
            provider=self.provider.name,
            spec=spec,
            memory=memory.snapshot(),
            scene=scene,
            initial_report=initial,
            final_report=report,
            iterations=iteration,
            passed=report.passed,
            refined=report.passed and not initial.passed,
            fault_injected=fault,
            trace=tracer.steps,
            total_ms=round((time.perf_counter() - started) * 1000, 2),
        )
