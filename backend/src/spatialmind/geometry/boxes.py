"""Axis-aligned box geometry for top-down (2D footprint) reasoning.

Everything here is pure deterministic math. No LLM is involved in collision, bounds or
distance computation (see proposal: "semantic intelligence from AI, geometric certainty
from computation").

Conventions: x runs west->east, y runs south->north. Rotation is degrees CCW. At rotation 0
the front of an object faces south (-y); see ``spatialmind.catalog``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from spatialmind.schemas import Opening, OpeningKind, PlacedObject, Room, Wall

EPS = 1e-6

# Unit vector of the object's front for each right-angle rotation (CCW degrees).
_FRONT: dict[int, tuple[int, int]] = {0: (0, -1), 90: (1, 0), 180: (0, 1), 270: (-1, 0)}

# Rotation an object needs so that its back is against the given wall (front faces the room).
WALL_ROTATION: dict[Wall, int] = {Wall.NORTH: 0, Wall.SOUTH: 180, Wall.EAST: 270, Wall.WEST: 90}


@dataclass(frozen=True)
class Box:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def depth(self) -> float:
        return self.max_y - self.min_y

    @property
    def center(self) -> tuple[float, float]:
        return ((self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2)

    def overlap_area(self, other: Box) -> float:
        ox = min(self.max_x, other.max_x) - max(self.min_x, other.min_x)
        oy = min(self.max_y, other.max_y) - max(self.min_y, other.min_y)
        return ox * oy if ox > EPS and oy > EPS else 0.0

    def overlaps(self, other: Box) -> bool:
        """True if the interiors intersect. Touching edges do not count."""
        return self.overlap_area(other) > 0.0

    def gap(self, other: Box) -> float:
        """Euclidean distance between the boxes (0 when touching or overlapping)."""
        dx = max(self.min_x - other.max_x, other.min_x - self.max_x, 0.0)
        dy = max(self.min_y - other.max_y, other.min_y - self.max_y, 0.0)
        return math.hypot(dx, dy)


def footprint(obj: PlacedObject) -> Box:
    """Top-down footprint of an object, accounting for its rotation."""
    w, d = (obj.depth, obj.width) if obj.rotation in (90, 270) else (obj.width, obj.depth)
    return Box(obj.x - w / 2, obj.y - d / 2, obj.x + w / 2, obj.y + d / 2)


def front_vector(rotation: int) -> tuple[int, int]:
    return _FRONT[rotation % 360]


def front_zone(obj: PlacedObject, clearance: float) -> Box:
    """The free area required in front of an object (e.g. to open a wardrobe or sit)."""
    box = footprint(obj)
    fx, fy = front_vector(obj.rotation)
    if fx == 1:
        return Box(box.max_x, box.min_y, box.max_x + clearance, box.max_y)
    if fx == -1:
        return Box(box.min_x - clearance, box.min_y, box.min_x, box.max_y)
    if fy == 1:
        return Box(box.min_x, box.max_y, box.max_x, box.max_y + clearance)
    return Box(box.min_x, box.min_y - clearance, box.max_x, box.min_y)


def room_box(room: Room) -> Box:
    return Box(0.0, 0.0, room.width, room.depth)


def wall_gap(obj: PlacedObject, wall: Wall, room: Room) -> float:
    """Distance from the object's footprint edge to the given wall (negative if outside)."""
    box = footprint(obj)
    if wall == Wall.NORTH:
        return room.depth - box.max_y
    if wall == Wall.SOUTH:
        return box.min_y
    if wall == Wall.EAST:
        return room.width - box.max_x
    return box.min_x


def opening_segment(room: Room, opening: Opening) -> Box:
    """The opening as a zero-thickness box lying on its wall."""
    half = opening.width / 2
    lo, hi = opening.offset - half, opening.offset + half
    if opening.wall == Wall.NORTH:
        return Box(lo, room.depth, hi, room.depth)
    if opening.wall == Wall.SOUTH:
        return Box(lo, 0.0, hi, 0.0)
    if opening.wall == Wall.EAST:
        return Box(room.width, lo, room.width, hi)
    return Box(0.0, lo, 0.0, hi)


def door_swing_zone(room: Room, opening: Opening) -> Box:
    """Square area inside the room in front of a door that must stay free."""
    assert opening.kind == OpeningKind.DOOR
    seg = opening_segment(room, opening)
    reach = opening.width
    if opening.wall == Wall.NORTH:
        return Box(seg.min_x, room.depth - reach, seg.max_x, room.depth)
    if opening.wall == Wall.SOUTH:
        return Box(seg.min_x, 0.0, seg.max_x, reach)
    if opening.wall == Wall.EAST:
        return Box(room.width - reach, seg.min_y, room.width, seg.max_y)
    return Box(0.0, seg.min_y, reach, seg.max_y)
