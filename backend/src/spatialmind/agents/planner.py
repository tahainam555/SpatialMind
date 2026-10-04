"""Spatial Planning agent (Agent 2): deterministic, constraint-aware layout planning.

The LLM never produces coordinates. Instead the planner enumerates candidate poses
(wall-snapped for wall furniture, a grid for free-standing items), discards any that violate
hard geometric rules (collision, bounds, doors, windows, clearance) and scores the rest by
how well they satisfy the user's constraints. Planning state lives in ``SpatialMemory`` so a
refinement pass can repair only the objects that verification flagged.
"""

from __future__ import annotations

import math
from collections.abc import Iterator

from spatialmind.catalog import CATALOG, CatalogEntry
from spatialmind.geometry.boxes import (
    WALL_ROTATION,
    Box,
    footprint,
    front_vector,
    wall_gap,
)
from spatialmind.geometry.verifier import (
    AWAY_DEFAULT,
    NEAR_DEFAULT,
    WALL_TOLERANCE,
    VerificationReport,
    check_bounds,
    check_clearance,
    check_collisions,
    check_openings,
    resolve_targets,
    verify,
)
from spatialmind.memory import Pose, SpatialMemory
from spatialmind.schemas import Constraint, ConstraintType, PlacedObject, SceneSpec, Wall

GRID_STEP = 0.25  # metres between candidate positions
MULTI_START = 10  # number of anchor poses tried by plan()
MIN_START_SPACING = 0.5  # metres: minimum spacing between anchor poses with the same rotation
_COMPANIONS = frozenset({"chair", "nightstand", "coffee_table"})  # placed after their anchors

# Default design rules added when the user does not specify them.
_DEFAULT_NEAR: dict[str, tuple[str, float]] = {
    "nightstand": ("bed", 0.6),
    "chair": ("desk", 0.3),
    "coffee_table": ("sofa", 0.9),
}
_DEFAULT_AWAY: dict[str, tuple[str, float]] = {"tv_stand": ("sofa", 2.0)}

# Objects that should face a partner object (front vector pointing at the partner).
_FACING: dict[str, tuple[str, ...]] = {
    "chair": ("desk",),
    "tv_stand": ("sofa",),
    "armchair": ("tv_stand",),
}
# Placed first (in this order) so that dependent objects can be positioned relative to them.
_ANCHORS = ("bed", "sofa", "tv_stand")


def instance_ids(spec: SceneSpec) -> list[tuple[str, str]]:
    """Expand object requests into unique (id, category) instances: bed_1, chair_1, chair_2..."""
    counts: dict[str, int] = {}
    out: list[tuple[str, str]] = []
    for req in spec.objects:
        for _ in range(req.quantity):
            counts[req.category] = counts.get(req.category, 0) + 1
            out.append((f"{req.category}_{counts[req.category]}", req.category))
    return out


def with_defaults(spec: SceneSpec) -> list[Constraint]:
    """User constraints plus default design rules for categories that are present."""
    present = {o.category for o in spec.objects}
    constraints = list(spec.constraints)
    has_wall = {c.subject for c in constraints if c.type == ConstraintType.AGAINST_WALL}
    has_near = {c.subject for c in constraints if c.type == ConstraintType.NEAR}
    has_away = {c.subject for c in constraints if c.type == ConstraintType.AWAY_FROM}
    for category in sorted(present):
        entry = CATALOG[category]
        if not entry.freestanding and category not in has_wall:
            constraints.append(Constraint(type=ConstraintType.AGAINST_WALL, subject=category))
        near = _DEFAULT_NEAR.get(category)
        if near and near[0] in present and category not in has_near:
            constraints.append(
                Constraint(
                    type=ConstraintType.NEAR, subject=category, target=near[0], distance=near[1]
                )
            )
        away = _DEFAULT_AWAY.get(category)
        if away and away[0] in present and category not in has_away:
            constraints.append(
                Constraint(
                    type=ConstraintType.AWAY_FROM,
                    subject=category,
                    target=away[0],
                    distance=away[1],
                )
            )
    return constraints


def new_memory(spec: SceneSpec) -> SpatialMemory:
    memory = SpatialMemory(room=spec.resolved_room, constraints=with_defaults(spec))
    memory.unplaced = [oid for oid, _ in instance_ids(spec)]
    memory.log("init", f"{len(memory.unplaced)} objects to place, {len(memory.constraints)} rules")
    return memory


def _order(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    def key(item: tuple[str, str]) -> tuple[int, int, float, str]:
        entry = CATALOG[item[1]]
        rank = _ANCHORS.index(item[1]) if item[1] in _ANCHORS else len(_ANCHORS)
        return (item[1] in _COMPANIONS, rank, -entry.width * entry.depth, item[0])

    return sorted(items, key=key)


# -- candidate generation -------------------------------------------------------------


def _steps(lo: float, hi: float) -> Iterator[float]:
    if hi < lo:
        return
    n = int(math.floor((hi - lo) / GRID_STEP + 1e-9))
    for i in range(n + 1):
        yield round(lo + i * GRID_STEP, 4)
    if (hi - lo) - n * GRID_STEP > 1e-6:
        yield round(hi, 4)


def candidate_poses(memory: SpatialMemory, entry: CatalogEntry) -> Iterator[Pose]:
    room = memory.room
    if entry.freestanding:
        for rot in (0, 90, 180, 270):
            w, d = (entry.depth, entry.width) if rot in (90, 270) else (entry.width, entry.depth)
            for x in _steps(w / 2, room.width - w / 2):
                for y in _steps(d / 2, room.depth - d / 2):
                    yield (x, y, rot)
        return
    for wall in (Wall.NORTH, Wall.WEST, Wall.EAST, Wall.SOUTH):
        rot = WALL_ROTATION[wall]
        w, d = (entry.depth, entry.width) if rot in (90, 270) else (entry.width, entry.depth)
        if wall in (Wall.NORTH, Wall.SOUTH):
            y = room.depth - d / 2 if wall == Wall.NORTH else d / 2
            for x in _steps(w / 2, room.width - w / 2):
                yield (x, round(y, 4), rot)
        else:
            x = room.width - w / 2 if wall == Wall.EAST else w / 2
            for y in _steps(d / 2, room.depth - d / 2):
                yield (round(x, 4), y, rot)


# -- feasibility and scoring ----------------------------------------------------------


def _feasible(memory: SpatialMemory, obj: PlacedObject) -> bool:
    """Hard geometric rules, evaluated with the candidate temporarily inserted."""
    memory.objects[obj.id] = obj
    try:
        return not (
            check_bounds(memory)
            or check_collisions(memory)
            or check_openings(memory)
            or check_clearance(memory)
        )
    finally:
        del memory.objects[obj.id]


def _gap_to(box: Box, targets: list[tuple[str, Box]], self_id: str) -> float | None:
    gaps = [box.gap(tbox) for tid, tbox in targets if tid != self_id]
    return min(gaps) if gaps else None


def _score(memory: SpatialMemory, obj: PlacedObject) -> float:
    box = footprint(obj)
    score = 0.0
    for c in memory.constraints:
        is_subject = c.subject in (obj.id, obj.category)
        is_target = c.target is not None and c.target in (obj.id, obj.category)
        if c.type == ConstraintType.AGAINST_WALL and is_subject:
            walls = [c.wall] if c.wall else list(Wall)
            wall_dist = min(wall_gap(obj, w, memory.room) for w in walls)
            score += 2.0 if wall_dist <= WALL_TOLERANCE else -wall_dist
        elif c.type in (ConstraintType.NEAR, ConstraintType.AWAY_FROM) and (
            is_subject or is_target
        ):
            partner_ref = c.target if is_subject else c.subject
            assert partner_ref is not None
            partner_gap = _gap_to(box, resolve_targets(memory, partner_ref), obj.id)
            if partner_gap is None:
                continue  # partner not placed yet; it will be scored when it is placed
            gap = partner_gap
            if c.type == ConstraintType.NEAR:
                limit = c.distance or NEAR_DEFAULT
                score += (3.0 + (1 - gap / limit) * 0.5) if gap <= limit else -(gap - limit)
            else:
                limit = c.distance or AWAY_DEFAULT
                score += (3.0 + min(gap, 2 * limit) * 0.1) if gap >= limit else -(limit - gap) * 2
    for partner_category in _FACING.get(obj.category, ()):
        partners = memory.resolve(partner_category)
        if partners:  # face the partner: front vector aligned with the direction towards it
            dx, dy = partners[0].x - obj.x, partners[0].y - obj.y
            norm = math.hypot(dx, dy) or 1.0
            fx, fy = front_vector(obj.rotation)
            score += 2.0 * (fx * dx + fy * dy) / norm
            break
    return score


def ranked_poses(
    memory: SpatialMemory, object_id: str, category: str
) -> list[tuple[float, PlacedObject]]:
    """All feasible, non-rejected poses for an object, best first (stable order on ties)."""
    entry = CATALOG[category]
    scored: list[tuple[float, PlacedObject]] = []
    for x, y, rot in candidate_poses(memory, entry):
        if memory.is_rejected(object_id, (x, y, rot)):
            continue
        obj = PlacedObject(
            id=object_id,
            category=category,
            width=entry.width,
            depth=entry.depth,
            height=entry.height,
            x=x,
            y=y,
            rotation=rot,
        )
        if _feasible(memory, obj):
            scored.append((_score(memory, obj), obj))
    scored.sort(key=lambda item: -item[0])  # sort is stable, so ties keep generation order
    return scored


def place_object(memory: SpatialMemory, object_id: str, category: str) -> bool:
    """Place a single object at its best feasible pose. Returns False if none exists."""
    ranked = ranked_poses(memory, object_id, category)
    if not ranked:
        if object_id not in memory.unplaced:
            memory.unplaced.append(object_id)
        memory.log("fail", f"no feasible pose for {object_id}")
        return False
    memory.place(ranked[0][1])
    return True


def _diverse(ranked: list[tuple[float, PlacedObject]], count: int) -> list[PlacedObject]:
    """Pick up to ``count`` high-scoring poses that are spread out (not 0.25 m neighbours)."""
    chosen: list[PlacedObject] = []
    for _, obj in ranked:
        if all(
            o.rotation != obj.rotation or math.hypot(o.x - obj.x, o.y - obj.y) >= MIN_START_SPACING
            for o in chosen
        ):
            chosen.append(obj)
            if len(chosen) == count:
                break
    return chosen


def plan(spec: SceneSpec, starts: int = MULTI_START) -> SpatialMemory:
    """Initial planning pass: place every requested object.

    Greedy placement can paint itself into a corner (e.g. a bed pushed into a corner leaves no
    room for two nightstands), so the anchor object is tried at several spread-out poses and the
    best complete layout (by verifier score) wins. Fully deterministic.
    """
    base = new_memory(spec)
    order = _order(instance_ids(spec))
    first_id, first_category = order[0]
    starts_poses: list[PlacedObject | None] = list(
        _diverse(ranked_poses(base, first_id, first_category), starts)
    ) or [None]

    best: tuple[tuple[bool, float, int], SpatialMemory] | None = None
    for start in starts_poses:
        memory = base.model_copy(deep=True)
        if start is not None:
            memory.place(start)
        for object_id, category in order[1:] if start is not None else order:
            place_object(memory, object_id, category)
        report = verify(memory)
        key = (report.passed, report.score, -len(memory.unplaced))
        if best is None or key > best[0]:
            best = (key, memory)
        if report.passed and report.score >= 1.0:
            break
    assert best is not None
    memory = best[1]
    memory.log("plan", f"placed {len(memory.objects)}, unplaced {len(memory.unplaced)}")
    return memory


def replan(memory: SpatialMemory, report: VerificationReport) -> SpatialMemory:
    """Repair a layout using structured verifier feedback.

    Objects named in violations are lifted out (their old pose is remembered as rejected, so it
    is never chosen again) and re-placed. Everything else stays where it was.
    """
    memory.iteration += 1
    flagged = report.violating_objects()
    memory.log("replan", f"repairing {', '.join(flagged) if flagged else 'nothing'}")
    items: list[tuple[str, str]] = []
    for object_id in flagged:
        obj = memory.objects.get(object_id)
        if obj is not None:
            memory.remove(object_id, reject_pose=True)
            items.append((object_id, obj.category))
        elif object_id in memory.unplaced:
            items.append((object_id, object_id.rsplit("_", 1)[0]))
    for object_id, category in _order(items):
        place_object(memory, object_id, category)
    return memory
