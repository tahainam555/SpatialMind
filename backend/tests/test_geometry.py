import pytest

from spatialmind.catalog import CATALOG
from spatialmind.geometry.boxes import (
    Box,
    door_swing_zone,
    footprint,
    front_vector,
    front_zone,
    opening_segment,
    wall_gap,
)
from spatialmind.geometry.verifier import evaluate_constraint, verify
from spatialmind.memory import SpatialMemory
from spatialmind.schemas import (
    Constraint,
    ConstraintType,
    PlacedObject,
    RoomType,
    Wall,
    default_room,
)

# Default bedroom: 4x4 m, door on south wall (x 2.85..3.75), window on north wall (x 1.3..2.7)


def mk(oid: str, category: str, x: float, y: float, rot: int = 0) -> PlacedObject:
    e = CATALOG[category]
    return PlacedObject(
        id=oid, category=category, width=e.width, depth=e.depth, height=e.height, x=x, y=y,
        rotation=rot,
    )  # fmt: skip


def memory(*objs: PlacedObject, constraints: list[Constraint] | None = None) -> SpatialMemory:
    mem = SpatialMemory(room=default_room(RoomType.BEDROOM), constraints=constraints or [])
    for o in objs:
        mem.place(o)
    return mem


def valid_layout() -> list[PlacedObject]:
    return [
        mk("bed_1", "bed", 1.0, 1.8, 90),  # against west wall, faces east
        mk("wardrobe_1", "wardrobe", 3.7, 2.0, 270),  # against east wall, faces west
        mk("desk_1", "desk", 2.0, 3.7, 0),  # against north wall under the window
        mk("chair_1", "chair", 2.0, 2.9, 0),
    ]


# -- boxes ----------------------------------------------------------------------------


def test_footprint_swaps_extents_on_quarter_turns() -> None:
    bed = mk("b", "bed", 2, 2, 0)
    assert footprint(bed).width == pytest.approx(1.6)
    rotated = mk("b", "bed", 2, 2, 90)
    assert footprint(rotated).width == pytest.approx(2.0)
    assert footprint(rotated).depth == pytest.approx(1.6)


def test_touching_boxes_do_not_overlap_but_have_zero_gap() -> None:
    a, b = Box(0, 0, 1, 1), Box(1, 0, 2, 1)
    assert not a.overlaps(b)
    assert a.gap(b) == 0
    assert Box(0, 0, 2, 2).overlaps(Box(1, 1, 3, 3))
    assert Box(0, 0, 1, 1).gap(Box(4, 5, 5, 6)) == pytest.approx(5.0)  # 3-4-5 triangle


def test_front_zone_for_each_rotation() -> None:
    for rot, (fx, fy) in {0: (0, -1), 90: (1, 0), 180: (0, 1), 270: (-1, 0)}.items():
        assert front_vector(rot) == (fx, fy)
        obj = mk("w", "wardrobe", 5, 5, rot)
        box, zone = footprint(obj), front_zone(obj, 0.7)
        assert not box.overlaps(zone)
        assert box.gap(zone) == 0
        cx, cy = zone.center
        bx, by = box.center
        assert (cx - bx) * fx + (cy - by) * fy > 0  # zone lies in front of the object


def test_wall_gap_and_opening_geometry() -> None:
    room = default_room(RoomType.BEDROOM)
    obj = mk("d", "desk", 2.0, 3.7)
    assert wall_gap(obj, Wall.NORTH, room) == pytest.approx(0.0)
    assert wall_gap(obj, Wall.SOUTH, room) == pytest.approx(3.4)
    assert wall_gap(obj, Wall.WEST, room) == pytest.approx(1.4)
    assert wall_gap(obj, Wall.EAST, room) == pytest.approx(1.4)
    window = next(o for o in room.openings if o.kind.value == "window")
    seg = opening_segment(room, window)
    assert (seg.min_x, seg.max_x, seg.min_y) == (pytest.approx(1.3), pytest.approx(2.7), 4.0)
    door = next(o for o in room.openings if o.kind.value == "door")
    zone = door_swing_zone(room, door)
    assert zone.max_y == pytest.approx(0.9)


# -- verifier -------------------------------------------------------------------------


def test_valid_layout_passes() -> None:
    cons = [
        Constraint(type=ConstraintType.NEAR, subject="desk", target="window"),
        Constraint(type=ConstraintType.AWAY_FROM, subject="desk", target="bed", distance=0.5),
        Constraint(type=ConstraintType.AGAINST_WALL, subject="bed", wall=Wall.WEST),
        Constraint(type=ConstraintType.AGAINST_WALL, subject="wardrobe"),
        Constraint(type=ConstraintType.CLEARANCE, subject="wardrobe", distance=0.7),
    ]
    report = verify(memory(*valid_layout(), constraints=cons))
    assert report.violations == []
    assert report.passed
    assert report.score == 1.0
    assert report.metrics["constraint_satisfaction"] == 1.0


def test_collision_detected() -> None:
    report = verify(memory(mk("a", "bed", 2, 2), mk("b", "bed", 2.5, 2)))
    assert report.metrics["collisions"] == 1
    assert not report.passed
    assert report.violating_objects() == ["a", "b"]


def test_out_of_bounds_detected() -> None:
    report = verify(memory(mk("bed_1", "bed", 0.5, 2.0)))
    assert report.metrics["boundary_violations"] == 1
    assert report.violations[0].kind == "out_of_bounds"


def test_door_blocking_detected() -> None:
    report = verify(memory(mk("dresser_1", "dresser", 3.3, 0.4, 180)))
    assert report.metrics["opening_blocks"] == 1


def test_tall_object_blocks_window_but_low_desk_does_not() -> None:
    assert verify(memory(mk("desk_1", "desk", 2.0, 3.7))).metrics["opening_blocks"] == 0
    blocked = verify(memory(mk("wardrobe_1", "wardrobe", 2.0, 3.7)))
    assert any(v.kind == "blocks_window" for v in blocked.violations)


def test_clearance_violation_and_chair_exemption() -> None:
    bad = verify(memory(mk("wardrobe_1", "wardrobe", 2.0, 3.7), mk("bed_1", "bed", 2.0, 2.4)))
    assert bad.metrics["clearance_violations"] >= 1
    ok = verify(memory(mk("desk_1", "desk", 2.0, 3.7), mk("chair_1", "chair", 2.0, 3.0)))
    assert ok.metrics["clearance_violations"] == 0


def test_unplaced_object_is_a_hard_violation() -> None:
    mem = memory(mk("bed_1", "bed", 1.0, 1.8, 90))
    mem.unplaced.append("desk_1")
    report = verify(mem)
    assert report.metrics["unplaced"] == 1
    assert not report.passed


def test_constraint_failures_reported_with_detail() -> None:
    cons = [
        Constraint(type=ConstraintType.NEAR, subject="desk", target="window", distance=0.3),
        Constraint(type=ConstraintType.AWAY_FROM, subject="desk", target="bed"),
        Constraint(type=ConstraintType.AGAINST_WALL, subject="bed", wall=Wall.NORTH),
        Constraint(type=ConstraintType.NEAR, subject="ghost", target="bed"),
        Constraint(type=ConstraintType.NEAR, subject="bed", target="spaceship"),
    ]
    layout = [mk("bed_1", "bed", 1.0, 1.8, 90), mk("desk_1", "desk", 2.0, 2.5)]
    report = verify(memory(*layout, constraints=cons))
    results = {r.constraint: r for r in report.constraint_results}
    assert not any(r.satisfied for r in results.values())
    assert "away" in results["NEAR(desk, window)"].detail
    assert "only" in results["AWAY_FROM(desk, bed)"].detail
    assert "from the wall" in results["AGAINST_WALL(bed, north)"].detail
    assert results["NEAR(ghost, bed)"].detail == "subject not placed"
    assert results["NEAR(bed, spaceship)"].detail == "target not found"
    assert report.metrics["constraint_satisfaction"] == 0.0
    assert any(v.kind == "constraint" and not v.hard for v in report.violations)


def test_clearance_constraint_overrides_catalog_default() -> None:
    cons = [Constraint(type=ConstraintType.CLEARANCE, subject="bed", distance=1.5)]
    layout = [mk("bed_1", "bed", 1.0, 1.8, 90), mk("wardrobe_1", "wardrobe", 3.7, 2.0, 270)]
    mem = memory(*layout, constraints=cons)
    assert not evaluate_constraint(mem, cons[0]).satisfied
    assert verify(mem).metrics["clearance_violations"] >= 1


def test_near_ignores_self_when_target_is_same_category() -> None:
    cons = [Constraint(type=ConstraintType.NEAR, subject="chair", target="chair")]
    mem = memory(mk("chair_1", "chair", 1, 1), constraints=cons)
    assert not evaluate_constraint(mem, cons[0]).satisfied
