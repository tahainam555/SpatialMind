"""Structured scene specification: the contract between Agent 1 and the planner."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from spatialmind.catalog import normalize_category


class Wall(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class OpeningKind(str, Enum):
    DOOR = "door"
    WINDOW = "window"


class RoomType(str, Enum):
    BEDROOM = "bedroom"
    LIVING_ROOM = "living_room"
    OFFICE = "office"


class ConstraintType(str, Enum):
    NEAR = "NEAR"
    AWAY_FROM = "AWAY_FROM"
    AGAINST_WALL = "AGAINST_WALL"
    CLEARANCE = "CLEARANCE"


class Opening(BaseModel):
    """A door or window on a wall.

    ``offset`` is the distance of the opening centre along the wall, measured from the
    west end for north/south walls and from the south end for east/west walls.
    """

    kind: OpeningKind
    wall: Wall
    offset: float
    width: float = Field(default=1.0, gt=0)


class Room(BaseModel):
    """Rectangular room. x runs west->east (width), y runs south->north (depth)."""

    width: float = Field(gt=1.5, le=30)
    depth: float = Field(gt=1.5, le=30)
    height: float = Field(default=2.7, gt=1.5, le=6)
    openings: list[Opening] = Field(default_factory=list)

    def wall_length(self, wall: Wall) -> float:
        return self.width if wall in (Wall.NORTH, Wall.SOUTH) else self.depth

    @model_validator(mode="after")
    def _openings_fit(self) -> Room:
        for op in self.openings:
            half = op.width / 2
            if op.offset - half < -1e-9 or op.offset + half > self.wall_length(op.wall) + 1e-9:
                raise ValueError(f"{op.kind.value} on {op.wall.value} wall does not fit")
        return self


def default_room(room_type: RoomType) -> Room:
    """Sensible default room (with a door and a window) when none is specified."""
    if room_type == RoomType.LIVING_ROOM:
        return Room(
            width=5.0,
            depth=4.5,
            openings=[
                Opening(kind=OpeningKind.DOOR, wall=Wall.SOUTH, offset=0.8, width=0.9),
                Opening(kind=OpeningKind.WINDOW, wall=Wall.NORTH, offset=2.5, width=1.8),
            ],
        )
    if room_type == RoomType.OFFICE:
        return Room(
            width=3.5,
            depth=3.5,
            openings=[
                Opening(kind=OpeningKind.DOOR, wall=Wall.SOUTH, offset=0.7, width=0.9),
                Opening(kind=OpeningKind.WINDOW, wall=Wall.NORTH, offset=1.75, width=1.4),
            ],
        )
    return Room(
        width=4.0,
        depth=4.0,
        openings=[
            Opening(kind=OpeningKind.DOOR, wall=Wall.SOUTH, offset=3.3, width=0.9),
            Opening(kind=OpeningKind.WINDOW, wall=Wall.NORTH, offset=2.0, width=1.4),
        ],
    )


class ObjectRequest(BaseModel):
    category: str
    quantity: int = Field(default=1, ge=1, le=4)

    @field_validator("category")
    @classmethod
    def _known_category(cls, value: str) -> str:
        normalized = normalize_category(value)
        if normalized is None:
            raise ValueError(f"unknown furniture category: {value!r}")
        return normalized


class Constraint(BaseModel):
    """A spatial requirement. ``subject``/``target`` are object ids or categories; ``target``
    may also be an opening kind (``window`` / ``door``)."""

    type: ConstraintType
    subject: str
    target: str | None = None
    wall: Wall | None = None
    distance: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _required_fields(self) -> Constraint:
        if self.type in (ConstraintType.NEAR, ConstraintType.AWAY_FROM) and not self.target:
            raise ValueError(f"{self.type.value} requires a target")
        if self.type == ConstraintType.CLEARANCE and self.distance is None:
            raise ValueError("CLEARANCE requires a distance")
        return self

    def describe(self) -> str:
        if self.type in (ConstraintType.NEAR, ConstraintType.AWAY_FROM):
            return f"{self.type.value}({self.subject}, {self.target})"
        if self.type == ConstraintType.AGAINST_WALL:
            wall = f", {self.wall.value}" if self.wall else ""
            return f"AGAINST_WALL({self.subject}{wall})"
        return f"CLEARANCE({self.subject}, {self.distance}m)"


class SceneSpec(BaseModel):
    room_type: RoomType = RoomType.BEDROOM
    room: Room | None = None
    objects: list[ObjectRequest] = Field(min_length=1)
    constraints: list[Constraint] = Field(default_factory=list)
    style: str | None = None

    @model_validator(mode="after")
    def _fill_room(self) -> SceneSpec:
        if self.room is None:
            self.room = default_room(self.room_type)
        return self

    @property
    def resolved_room(self) -> Room:
        assert self.room is not None
        return self.room


class PlacedObject(BaseModel):
    """An object with a concrete pose. (x, y) is the footprint centre in metres and
    ``rotation`` is degrees counter-clockwise (0, 90, 180 or 270)."""

    id: str
    category: str
    width: float
    depth: float
    height: float
    x: float
    y: float
    rotation: int = 0

    @field_validator("rotation")
    @classmethod
    def _right_angle(cls, value: int) -> int:
        if value % 90 != 0:
            raise ValueError("rotation must be a multiple of 90 degrees")
        return value % 360
