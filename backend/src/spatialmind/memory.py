"""Persistent spatial memory: the structured scene state shared across agent iterations.

The memory records the room, every placed object (pose + extents), the active constraints,
placements that were previously rejected by verification, and an event log. Persisting this
across planning iterations lets the planner refine an existing layout instead of restarting.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from spatialmind.schemas import Constraint, PlacedObject, Room

Pose = tuple[float, float, int]


class MemoryEvent(BaseModel):
    iteration: int
    action: str
    detail: str


class SpatialMemory(BaseModel):
    room: Room
    constraints: list[Constraint] = Field(default_factory=list)
    objects: dict[str, PlacedObject] = Field(default_factory=dict)
    rejected_poses: dict[str, list[Pose]] = Field(default_factory=dict)
    unplaced: list[str] = Field(default_factory=list)
    events: list[MemoryEvent] = Field(default_factory=list)
    iteration: int = 0

    # -- object state ---------------------------------------------------------------
    def place(self, obj: PlacedObject) -> None:
        self.objects[obj.id] = obj
        if obj.id in self.unplaced:
            self.unplaced.remove(obj.id)
        self.log("place", f"{obj.id} at ({obj.x:.2f}, {obj.y:.2f}) rot {obj.rotation}")

    def remove(self, object_id: str, reject_pose: bool = False) -> PlacedObject | None:
        obj = self.objects.pop(object_id, None)
        if obj is not None:
            if reject_pose:
                self.rejected_poses.setdefault(object_id, []).append((obj.x, obj.y, obj.rotation))
            self.log("remove", f"{object_id} (rejected={reject_pose})")
        return obj

    def is_rejected(self, object_id: str, pose: Pose) -> bool:
        return any(
            abs(pose[0] - x) < 1e-6 and abs(pose[1] - y) < 1e-6 and pose[2] == r
            for x, y, r in self.rejected_poses.get(object_id, [])
        )

    # -- reference resolution ---------------------------------------------------------
    def resolve(self, ref: str) -> list[PlacedObject]:
        """Resolve an id or category reference to the placed objects it denotes."""
        if ref in self.objects:
            return [self.objects[ref]]
        return [o for o in self.objects.values() if o.category == ref]

    # -- bookkeeping ------------------------------------------------------------------
    def log(self, action: str, detail: str) -> None:
        self.events.append(MemoryEvent(iteration=self.iteration, action=action, detail=detail))

    def snapshot(self) -> dict[str, Any]:
        """JSON-serialisable view of the current scene state."""
        return self.model_dump(mode="json")
