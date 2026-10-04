"""Geometric verification (deterministic half of Agent 4) and constraint evaluation.

``verify`` inspects a ``SpatialMemory`` and returns a structured ``VerificationReport``. The
report doubles as machine-readable feedback for the planner's refinement loop.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from spatialmind.catalog import CATALOG
from spatialmind.geometry.boxes import (
    EPS,
    Box,
    door_swing_zone,
    footprint,
    front_zone,
    opening_segment,
    room_box,
    wall_gap,
)
from spatialmind.memory import SpatialMemory
from spatialmind.schemas import Constraint, ConstraintType, OpeningKind, PlacedObject, Wall

NEAR_DEFAULT = 1.0  # metres: default maximum gap for NEAR
AWAY_DEFAULT = 1.2  # metres: default minimum gap for AWAY_FROM
WALL_TOLERANCE = 0.05  # metres: gap that still counts as "against" a wall
WINDOW_SILL_HEIGHT = 0.9  # objects taller than this block a window they stand in front of

# Objects that are allowed inside another object's front clearance zone by design.
FRONT_ZONE_EXEMPT: dict[str, frozenset[str]] = {
    "desk": frozenset({"chair"}),
    "sofa": frozenset({"coffee_table", "armchair"}),
    "tv_stand": frozenset({"coffee_table", "sofa", "armchair"}),
    "armchair": frozenset({"coffee_table"}),
}

ViolationKind = Literal[
    "unplaced", "collision", "out_of_bounds", "blocks_door", "blocks_window", "clearance",
    "constraint",
]  # fmt: skip


class Violation(BaseModel):
    kind: ViolationKind
    objects: list[str]
    message: str
    magnitude: float = 0.0
    hard: bool = True


class ConstraintResult(BaseModel):
    constraint: str
    satisfied: bool
    detail: str


class VerificationReport(BaseModel):
    violations: list[Violation] = Field(default_factory=list)
    constraint_results: list[ConstraintResult] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    score: float = 0.0
    passed: bool = False

    def violating_objects(self) -> list[str]:
        seen: list[str] = []
        for v in self.violations:
            for oid in v.objects:
                if oid not in seen:
                    seen.append(oid)
        return seen


# -- hard geometric checks ------------------------------------------------------------


def check_unplaced(memory: SpatialMemory) -> list[Violation]:
    return [
        Violation(kind="unplaced", objects=[oid], message=f"{oid} could not be placed")
        for oid in memory.unplaced
    ]


def check_collisions(memory: SpatialMemory) -> list[Violation]:
    objs = list(memory.objects.values())
    out: list[Violation] = []
    for i, a in enumerate(objs):
        for b in objs[i + 1 :]:
            area = footprint(a).overlap_area(footprint(b))
            if area > 0:
                out.append(
                    Violation(
                        kind="collision",
                        objects=[a.id, b.id],
                        message=f"{a.id} overlaps {b.id} by {area:.2f} m^2",
                        magnitude=area,
                    )
                )
    return out


def check_bounds(memory: SpatialMemory) -> list[Violation]:
    room = room_box(memory.room)
    out: list[Violation] = []
    for obj in memory.objects.values():
        box = footprint(obj)
        excess = max(
            room.min_x - box.min_x,
            room.min_y - box.min_y,
            box.max_x - room.max_x,
            box.max_y - room.max_y,
            0.0,
        )
        if excess > EPS:
            out.append(
                Violation(
                    kind="out_of_bounds",
                    objects=[obj.id],
                    message=f"{obj.id} extends {excess:.2f} m outside the room",
                    magnitude=excess,
                )
            )
    return out


def check_openings(memory: SpatialMemory) -> list[Violation]:
    out: list[Violation] = []
    for opening in memory.room.openings:
        if opening.kind == OpeningKind.DOOR:
            zone = door_swing_zone(memory.room, opening)
            for obj in memory.objects.values():
                area = footprint(obj).overlap_area(zone)
                if area > 0:
                    out.append(
                        Violation(
                            kind="blocks_door",
                            objects=[obj.id],
                            message=f"{obj.id} blocks the {opening.wall.value} door",
                            magnitude=area,
                        )
                    )
        else:
            seg = opening_segment(memory.room, opening)
            for obj in memory.objects.values():
                if obj.height > WINDOW_SILL_HEIGHT and footprint(obj).gap(seg) <= WALL_TOLERANCE:
                    out.append(
                        Violation(
                            kind="blocks_window",
                            objects=[obj.id],
                            message=f"{obj.id} ({obj.height:.1f} m) blocks the "
                            f"{opening.wall.value} window",
                        )
                    )
    return out


def required_clearance(memory: SpatialMemory, obj: PlacedObject) -> float:
    entry = CATALOG.get(obj.category)
    required = entry.front_clearance if entry else 0.0
    for c in memory.constraints:
        if (
            c.type == ConstraintType.CLEARANCE
            and c.subject in (obj.id, obj.category)
            and c.distance is not None
        ):
            required = max(required, c.distance)
    return required


def check_clearance(memory: SpatialMemory) -> list[Violation]:
    out: list[Violation] = []
    for obj in memory.objects.values():
        clearance = required_clearance(memory, obj)
        if clearance <= 0:
            continue
        zone = front_zone(obj, clearance)
        exempt = FRONT_ZONE_EXEMPT.get(obj.category, frozenset())
        for other in memory.objects.values():
            if other.id == obj.id or other.category in exempt:
                continue
            area = footprint(other).overlap_area(zone)
            if area > 0:
                out.append(
                    Violation(
                        kind="clearance",
                        objects=[obj.id, other.id],
                        message=f"{other.id} intrudes into the {clearance:.1f} m clearance "
                        f"in front of {obj.id}",
                        magnitude=area,
                    )
                )
    return out


# -- constraint evaluation ------------------------------------------------------------


def resolve_targets(memory: SpatialMemory, ref: str) -> list[tuple[str, Box]]:
    placed = memory.resolve(ref)
    if placed:
        return [(o.id, footprint(o)) for o in placed]
    return [
        (f"{op.kind.value}@{op.wall.value}", opening_segment(memory.room, op))
        for op in memory.room.openings
        if op.kind.value == ref
    ]


def evaluate_constraint(memory: SpatialMemory, c: Constraint) -> ConstraintResult:
    desc = c.describe()
    subjects = memory.resolve(c.subject)
    if not subjects:
        return ConstraintResult(constraint=desc, satisfied=False, detail="subject not placed")

    if c.type == ConstraintType.CLEARANCE:
        bad = [
            v
            for v in check_clearance(memory)
            if v.objects[0] in {s.id for s in subjects}
        ]  # fmt: skip
        return ConstraintResult(
            constraint=desc,
            satisfied=not bad,
            detail="clear" if not bad else bad[0].message,
        )

    if c.type == ConstraintType.AGAINST_WALL:
        walls = [c.wall] if c.wall else list(Wall)
        for s in subjects:
            best = min(wall_gap(s, w, memory.room) for w in walls)
            if best > WALL_TOLERANCE:
                return ConstraintResult(
                    constraint=desc,
                    satisfied=False,
                    detail=f"{s.id} is {best:.2f} m from the wall",
                )
        return ConstraintResult(constraint=desc, satisfied=True, detail="against wall")

    targets = resolve_targets(memory, c.target or "")
    if not targets:
        return ConstraintResult(constraint=desc, satisfied=False, detail="target not found")

    for s in subjects:
        box = footprint(s)
        nearest = min(
            (box.gap(tbox) for tid, tbox in targets if tid != s.id), default=float("inf")
        )  # fmt: skip
        if c.type == ConstraintType.NEAR:
            limit = c.distance or NEAR_DEFAULT
            if nearest > limit:
                return ConstraintResult(
                    constraint=desc,
                    satisfied=False,
                    detail=f"{s.id} is {nearest:.2f} m away (max {limit:.2f} m)",
                )
        else:
            limit = c.distance or AWAY_DEFAULT
            if nearest < limit:
                return ConstraintResult(
                    constraint=desc,
                    satisfied=False,
                    detail=f"{s.id} is only {nearest:.2f} m away (min {limit:.2f} m)",
                )
    return ConstraintResult(constraint=desc, satisfied=True, detail="satisfied")


def _constraint_violations(
    memory: SpatialMemory, results: list[ConstraintResult]
) -> list[Violation]:
    out: list[Violation] = []
    for c, res in zip(memory.constraints, results, strict=True):
        if res.satisfied or c.type == ConstraintType.CLEARANCE:
            continue  # clearance failures are already reported as clearance violations
        involved = [o.id for o in memory.resolve(c.subject)]
        if c.target:
            involved += [o.id for o in memory.resolve(c.target)]
        out.append(
            Violation(
                kind="constraint",
                objects=involved,
                message=f"{res.constraint} violated: {res.detail}",
                hard=False,
            )
        )
    return out


# -- aggregate ------------------------------------------------------------------------


def verify(memory: SpatialMemory) -> VerificationReport:
    collisions = check_collisions(memory)
    bounds = check_bounds(memory)
    openings = check_openings(memory)
    clearance = check_clearance(memory)
    unplaced = check_unplaced(memory)
    results = [evaluate_constraint(memory, c) for c in memory.constraints]
    soft = _constraint_violations(memory, results)

    hard = unplaced + collisions + bounds + openings + clearance
    satisfied = sum(1 for r in results if r.satisfied)
    ratio = satisfied / len(results) if results else 1.0
    score = ratio * max(0.0, 1.0 - 0.15 * len(hard))
    metrics = {
        "objects_placed": float(len(memory.objects)),
        "collisions": float(len(collisions)),
        "boundary_violations": float(len(bounds)),
        "opening_blocks": float(len(openings)),
        "clearance_violations": float(len(clearance)),
        "unplaced": float(len(unplaced)),
        "constraints_total": float(len(results)),
        "constraints_satisfied": float(satisfied),
        "constraint_satisfaction": ratio,
    }
    return VerificationReport(
        violations=hard + soft,
        constraint_results=results,
        metrics=metrics,
        score=round(score, 4),
        passed=not hard and satisfied == len(results),
    )
