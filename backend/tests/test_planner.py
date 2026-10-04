from spatialmind.agents.planner import (
    candidate_poses,
    instance_ids,
    new_memory,
    place_object,
    plan,
    replan,
    with_defaults,
)
from spatialmind.catalog import CATALOG
from spatialmind.geometry.verifier import verify
from spatialmind.schemas import (
    Constraint,
    ConstraintType,
    ObjectRequest,
    PlacedObject,
    RoomType,
    SceneSpec,
)


def bedroom_spec(**kw: object) -> SceneSpec:
    return SceneSpec(
        room_type=RoomType.BEDROOM,
        objects=[
            ObjectRequest(category="bed"),
            ObjectRequest(category="desk"),
            ObjectRequest(category="wardrobe"),
        ],
        constraints=[
            Constraint(type=ConstraintType.NEAR, subject="desk", target="window"),
            Constraint(type=ConstraintType.AWAY_FROM, subject="desk", target="bed"),
        ],
        **kw,  # type: ignore[arg-type]
    )


def test_instance_ids_expand_quantities() -> None:
    spec = SceneSpec(objects=[ObjectRequest(category="chair", quantity=2)])
    assert instance_ids(spec) == [("chair_1", "chair"), ("chair_2", "chair")]


def test_with_defaults_adds_rules_without_duplicating_user_rules() -> None:
    spec = SceneSpec(
        objects=[ObjectRequest(category="bed"), ObjectRequest(category="nightstand")],
        constraints=[Constraint(type=ConstraintType.AGAINST_WALL, subject="bed")],
    )
    described = [c.describe() for c in with_defaults(spec)]
    assert described.count("AGAINST_WALL(bed)") == 1
    assert "AGAINST_WALL(nightstand)" in described
    assert "NEAR(nightstand, bed)" in described


def test_candidates_are_in_bounds_and_wall_snapped() -> None:
    memory = new_memory(bedroom_spec())
    poses = list(candidate_poses(memory, CATALOG["wardrobe"]))
    assert poses
    ends = {x for x, _, rot in poses if rot == 0}
    assert min(ends) == 0.6 and max(ends) == 3.4  # includes both ends of the wall
    chair_poses = list(candidate_poses(memory, CATALOG["chair"]))
    assert len(chair_poses) > len(poses) // 2


def test_plan_produces_a_valid_bedroom() -> None:
    memory = plan(bedroom_spec())
    assert memory.unplaced == []
    report = verify(memory)
    assert report.passed, [v.message for v in report.violations]
    assert report.metrics["constraint_satisfaction"] == 1.0
    assert report.score == 1.0


def test_planning_is_deterministic() -> None:
    a = plan(bedroom_spec()).snapshot()["objects"]
    b = plan(bedroom_spec()).snapshot()["objects"]
    assert a == b


def test_full_bedroom_with_companions() -> None:
    spec = SceneSpec(
        objects=[
            ObjectRequest(category="bed"),
            ObjectRequest(category="nightstand", quantity=2),
            ObjectRequest(category="desk"),
            ObjectRequest(category="chair"),
            ObjectRequest(category="wardrobe"),
        ],
        constraints=[Constraint(type=ConstraintType.NEAR, subject="desk", target="window")],
    )
    memory = plan(spec)
    report = verify(memory)
    assert memory.unplaced == []
    assert report.passed, [v.message for v in report.violations]


def test_impossible_object_ends_up_unplaced() -> None:
    spec = SceneSpec(
        room_type=RoomType.OFFICE,
        objects=[ObjectRequest(category="sofa", quantity=4), ObjectRequest(category="bed")],
    )
    memory = plan(spec)
    assert memory.unplaced
    assert not verify(memory).passed


def test_replan_repairs_a_colliding_object_and_never_reuses_its_pose() -> None:
    memory = plan(bedroom_spec())
    bed = memory.objects["bed_1"]
    desk = memory.objects["desk_1"]
    old_pose = (desk.x, desk.y, desk.rotation)
    # inject a fault: put the desk on top of the bed
    memory.objects["desk_1"] = PlacedObject(
        id="desk_1", category="desk", width=desk.width, depth=desk.depth, height=desk.height,
        x=bed.x, y=bed.y, rotation=0,
    )  # fmt: skip
    broken = verify(memory)
    assert broken.metrics["collisions"] >= 1

    replan(memory, broken)
    fixed = verify(memory)
    assert fixed.passed, [v.message for v in fixed.violations]
    assert memory.iteration == 1
    assert memory.is_rejected("desk_1", (bed.x, bed.y, 0))
    new = memory.objects["desk_1"]
    assert (new.x, new.y, new.rotation) != (bed.x, bed.y, 0)
    assert any(e.action == "replan" for e in memory.events)
    assert old_pose is not None


def test_replan_retries_unplaced_objects() -> None:
    memory = new_memory(bedroom_spec())
    assert memory.unplaced == ["bed_1", "desk_1", "wardrobe_1"]
    report = verify(memory)
    replan(memory, report)
    assert memory.unplaced == []
    assert verify(memory).passed


def test_place_object_returns_false_when_room_is_full() -> None:
    spec = SceneSpec(room_type=RoomType.OFFICE, objects=[ObjectRequest(category="bed")])
    memory = new_memory(spec)
    assert place_object(memory, "bed_1", "bed") is True
    assert place_object(memory, "bed_2", "bed") is True
    assert place_object(memory, "bed_3", "bed") is False
    assert "bed_3" in memory.unplaced
