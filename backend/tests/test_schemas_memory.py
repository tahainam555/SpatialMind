import pytest
from pydantic import ValidationError

from spatialmind.catalog import CATALOG, normalize_category
from spatialmind.memory import SpatialMemory
from spatialmind.schemas import (
    Constraint,
    ConstraintType,
    ObjectRequest,
    Opening,
    OpeningKind,
    PlacedObject,
    Room,
    RoomType,
    SceneSpec,
    Wall,
    default_room,
)


def test_normalize_category_handles_synonyms_and_plurals() -> None:
    assert normalize_category("Closet") == "wardrobe"
    assert normalize_category("couch") == "sofa"
    assert normalize_category("beds") == "bed"
    assert normalize_category("coffee table") == "coffee_table"
    assert normalize_category("spaceship") is None


def test_catalog_dimensions_are_positive() -> None:
    for entry in CATALOG.values():
        assert entry.width > 0 and entry.depth > 0 and entry.height > 0


def test_object_request_normalizes_and_rejects_unknown() -> None:
    assert ObjectRequest(category="closet").category == "wardrobe"
    with pytest.raises(ValidationError):
        ObjectRequest(category="jetpack")


def test_scene_spec_fills_default_room() -> None:
    spec = SceneSpec(room_type=RoomType.OFFICE, objects=[ObjectRequest(category="desk")])
    assert spec.resolved_room.width == 3.5
    kinds = {o.kind for o in spec.resolved_room.openings}
    assert kinds == {OpeningKind.DOOR, OpeningKind.WINDOW}


def test_scene_spec_requires_objects() -> None:
    with pytest.raises(ValidationError):
        SceneSpec(objects=[])


def test_opening_must_fit_wall() -> None:
    with pytest.raises(ValidationError):
        Room(
            width=3,
            depth=3,
            openings=[Opening(kind=OpeningKind.WINDOW, wall=Wall.NORTH, offset=2.9, width=1.0)],
        )


def test_constraint_validation() -> None:
    with pytest.raises(ValidationError):
        Constraint(type=ConstraintType.NEAR, subject="desk")
    with pytest.raises(ValidationError):
        Constraint(type=ConstraintType.CLEARANCE, subject="bed")
    c = Constraint(type=ConstraintType.NEAR, subject="desk", target="window")
    assert c.describe() == "NEAR(desk, window)"
    assert (
        "north"
        in Constraint(type=ConstraintType.AGAINST_WALL, subject="bed", wall=Wall.NORTH).describe()
    )
    assert (
        "0.8" in Constraint(type=ConstraintType.CLEARANCE, subject="bed", distance=0.8).describe()
    )


def test_placed_object_rotation_validation() -> None:
    obj = PlacedObject(id="a", category="bed", width=1, depth=1, height=1, x=0, y=0, rotation=450)
    assert obj.rotation == 90
    with pytest.raises(ValidationError):
        PlacedObject(id="a", category="bed", width=1, depth=1, height=1, x=0, y=0, rotation=45)


def _bed() -> PlacedObject:
    return PlacedObject(id="bed_1", category="bed", width=1.6, depth=2, height=0.6, x=1, y=1)


def test_memory_place_remove_and_resolve() -> None:
    mem = SpatialMemory(room=default_room(RoomType.BEDROOM))
    mem.unplaced.append("bed_1")
    mem.place(_bed())
    assert mem.unplaced == []
    assert mem.resolve("bed_1")[0].id == "bed_1"
    assert mem.resolve("bed")[0].id == "bed_1"
    assert mem.resolve("ghost") == []

    removed = mem.remove("bed_1", reject_pose=True)
    assert removed is not None
    assert mem.is_rejected("bed_1", (1, 1, 0))
    assert not mem.is_rejected("bed_1", (2, 1, 0))
    assert mem.remove("bed_1") is None


def test_memory_snapshot_is_json_serialisable() -> None:
    mem = SpatialMemory(room=default_room(RoomType.BEDROOM))
    mem.place(_bed())
    snap = mem.snapshot()
    assert snap["objects"]["bed_1"]["category"] == "bed"
    assert snap["events"][0]["action"] == "place"
    assert SpatialMemory.model_validate(snap).objects["bed_1"].x == 1
