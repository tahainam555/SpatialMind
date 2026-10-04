"""Scene Understanding agent (Agent 1): natural language -> validated SceneSpec.

The LLM is only asked for *semantics* (which furniture, which relations). Its JSON output is
validated against the pydantic schema; on failure the validation error is fed back and the
model is asked again. It is never asked for coordinates.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from spatialmind.agents.llm import LLMProvider
from spatialmind.catalog import CATALOG
from spatialmind.schemas import ConstraintType, Room, SceneSpec, Wall


class UnderstandingError(Exception):
    """Raised when the model cannot produce a valid scene specification."""


def build_system_prompt() -> str:
    categories = ", ".join(sorted(CATALOG))
    constraint_help = "\n".join(
        [
            f'- {ConstraintType.NEAR.value}: {{"type":"NEAR","subject":"desk","target":"window"}}'
            " (target may be a furniture category or the openings 'window'/'door')",
            f'- {ConstraintType.AWAY_FROM.value}: {{"type":"AWAY_FROM","subject":"desk",'
            '"target":"bed"}',
            f'- {ConstraintType.AGAINST_WALL.value}: {{"type":"AGAINST_WALL","subject":"bed",'
            f'"wall":"north"}} (wall is optional; one of {", ".join(w.value for w in Wall)})',
            f'- {ConstraintType.CLEARANCE.value}: {{"type":"CLEARANCE","subject":"wardrobe",'
            '"distance":0.8}} (free space in metres in front of the object)',
        ]
    )
    return (
        "You convert a user's description of an indoor room into a JSON scene specification.\n"
        "Return ONLY a JSON object with keys: room_type, objects, constraints, style.\n"
        "- room_type: one of bedroom, living_room, office.\n"
        f"- objects: list of {{category, quantity}}. Allowed categories: {categories}.\n"
        "- constraints: list of spatial requirements the user asked for. Types:\n"
        f"{constraint_help}\n"
        "- style: short style word or null.\n"
        "Do NOT output coordinates or room dimensions. Only include constraints the user "
        "stated or clearly implied. Do not invent furniture the user did not ask for."
    )


def _extract_json(raw: str) -> dict[str, object]:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("top-level JSON value must be an object")
    return data


def resize_room(room: Room, width: float | None, depth: float | None) -> Room:
    """Apply user-specified dimensions, keeping door/window positions valid on the new walls."""
    new_w = width or room.width
    new_d = depth or room.depth
    resized = Room(width=new_w, depth=new_d, height=room.height)
    openings = []
    for op in room.openings:
        length = resized.wall_length(op.wall)
        w = min(op.width, length - 0.2)
        offset = min(max(op.offset, w / 2 + 0.1), length - w / 2 - 0.1)
        openings.append(op.model_copy(update={"width": w, "offset": offset}))
    return Room(width=new_w, depth=new_d, height=room.height, openings=openings)


class UnderstandingAgent:
    def __init__(self, provider: LLMProvider, max_retries: int = 2) -> None:
        self.provider = provider
        self.max_retries = max_retries
        self.system = build_system_prompt()

    def understand(
        self,
        description: str,
        room_width: float | None = None,
        room_depth: float | None = None,
    ) -> SceneSpec:
        if not description.strip():
            raise UnderstandingError("description is empty")
        prompt = description.strip()
        last_error = ""
        for _ in range(self.max_retries + 1):
            try:
                raw = self.provider.generate_json(self.system, prompt)
            except Exception as exc:  # network, quota, auth... never crash the pipeline
                raise UnderstandingError(f"LLM provider error: {exc}") from exc
            try:
                spec = SceneSpec.model_validate(_extract_json(raw))
            except (ValueError, ValidationError) as exc:  # JSONDecodeError is a ValueError
                last_error = str(exc)
                prompt = (
                    f"{description.strip()}\n\nYour previous answer was invalid: {last_error}\n"
                    "Return corrected JSON only."
                )
                continue
            if room_width or room_depth:
                spec.room = resize_room(spec.resolved_room, room_width, room_depth)
            return spec
        raise UnderstandingError(
            f"could not produce a valid scene spec after {self.max_retries + 1} attempts: "
            f"{last_error}"
        )
