"""Scene Construction agent (Agent 3), mid-evaluation stub.

Blender / ``bpy`` execution and 3D-FUTURE asset retrieval arrive after the FYP-1 mid
evaluation. What exists now is the *contract*: a Blender-ready scene description built from the
spatial memory. The later Blender script will consume exactly this payload, so swapping the stub
for the real construction step will not change the planner or the verifier.

Blender convention: Z is up. Plan (x, y) maps to Blender (x, y); ``location`` is the centre of
the object's base-footprint at floor level, ``rotation_z_deg`` is CCW rotation about Z.
"""

from __future__ import annotations

from typing import Any

from spatialmind.memory import SpatialMemory


def construct_scene(memory: SpatialMemory) -> dict[str, Any]:
    room = memory.room
    return {
        "format": "spatialmind.scene/v1",
        "room": {
            "width": room.width,
            "depth": room.depth,
            "height": room.height,
            "openings": [op.model_dump(mode="json") for op in room.openings],
        },
        "objects": [
            {
                "id": obj.id,
                "category": obj.category,
                "asset": f"placeholder/{obj.category}",  # 3D-FUTURE asset id arrives later
                "location": [obj.x, obj.y, 0.0],
                "rotation_z_deg": obj.rotation,
                "dimensions": [obj.width, obj.depth, obj.height],
            }
            for obj in memory.objects.values()
        ],
    }
