"""Controlled furniture catalog.

The project uses a controlled asset library (see proposal: risk mitigation for asset
availability). Dimensions are in metres. These dimensions are the contract between the
planner (which needs footprints) and, later, the Blender construction agent (which maps
each category to a concrete 3D-FUTURE asset of similar size).

Local frame convention (rotation 0): width runs along local x, depth along local y and the
*front* of the object faces local -y (i.e. towards the south in the top-down plan).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogEntry:
    category: str
    width: float
    depth: float
    height: float
    front_clearance: float = 0.0
    freestanding: bool = False
    synonyms: tuple[str, ...] = ()


_ENTRIES: tuple[CatalogEntry, ...] = (
    CatalogEntry("bed", 1.6, 2.0, 0.6, front_clearance=0.6, synonyms=("double bed", "queen bed")),
    CatalogEntry("nightstand", 0.45, 0.4, 0.55, synonyms=("bedside table", "side table")),
    CatalogEntry("desk", 1.2, 0.6, 0.75, front_clearance=0.7, synonyms=("study table", "table")),
    CatalogEntry("chair", 0.5, 0.5, 0.9, freestanding=True, synonyms=("office chair", "stool")),
    CatalogEntry("wardrobe", 1.2, 0.6, 2.0, front_clearance=0.7, synonyms=("closet", "cupboard")),
    CatalogEntry("dresser", 1.0, 0.5, 0.85, front_clearance=0.5, synonyms=("chest of drawers",)),
    CatalogEntry("bookshelf", 0.8, 0.3, 1.8, front_clearance=0.4, synonyms=("bookcase",)),
    CatalogEntry("sofa", 2.0, 0.9, 0.85, front_clearance=0.5, synonyms=("couch",)),
    CatalogEntry("armchair", 0.8, 0.8, 0.85, front_clearance=0.4, synonyms=("lounge chair",)),
    CatalogEntry("coffee_table", 1.0, 0.5, 0.45, freestanding=True, synonyms=("coffee table",)),
    CatalogEntry("tv_stand", 1.2, 0.4, 0.5, front_clearance=0.8, synonyms=("tv", "tv unit")),
    CatalogEntry(
        "filing_cabinet", 0.45, 0.6, 0.7, front_clearance=0.5, synonyms=("cabinet", "file cabinet")
    ),
)

CATALOG: dict[str, CatalogEntry] = {e.category: e for e in _ENTRIES}

_SYNONYM_INDEX: dict[str, str] = {}
for _entry in _ENTRIES:
    _SYNONYM_INDEX[_entry.category] = _entry.category
    _SYNONYM_INDEX[_entry.category.replace("_", " ")] = _entry.category
    for _syn in _entry.synonyms:
        _SYNONYM_INDEX[_syn] = _entry.category


def normalize_category(name: str) -> str | None:
    """Map a free-text furniture name to a catalog category, or None if unknown."""
    key = name.strip().lower().replace("-", " ")
    if key in _SYNONYM_INDEX:
        return _SYNONYM_INDEX[key]
    if key.endswith("s") and key[:-1] in _SYNONYM_INDEX:  # naive plural: "beds"
        return _SYNONYM_INDEX[key[:-1]]
    return None


def get_entry(category: str) -> CatalogEntry:
    return CATALOG[category]
