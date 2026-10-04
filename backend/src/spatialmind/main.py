"""FastAPI application entrypoint."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from spatialmind import __version__
from spatialmind.agents.llm import build_provider
from spatialmind.agents.understanding import UnderstandingError
from spatialmind.catalog import CATALOG
from spatialmind.config import get_settings
from spatialmind.controller.pipeline import GenerationResult, Pipeline

EXAMPLES = [
    "Create a bedroom with a bed, desk and wardrobe, with the desk near the window "
    "and enough space for movement.",
    "A bedroom with a double bed, two nightstands, a wardrobe and a desk with a chair. "
    "Keep the desk near the window and away from the bed.",
    "A living room with a sofa, a coffee table, a tv stand and an armchair.",
    "A small study with a desk, a chair, a bookshelf and a filing cabinet. Desk near the window.",
]


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    room_width: float | None = Field(default=None, ge=2.0, le=15.0)
    room_depth: float | None = Field(default=None, ge=2.0, le=15.0)
    max_iterations: int = Field(default=3, ge=0, le=6)
    inject_fault: bool = False


@lru_cache
def get_pipeline() -> Pipeline:
    return Pipeline(build_provider(get_settings()))


def create_app(static_dir: str | None = None) -> FastAPI:
    app = FastAPI(title="SpatialMind API", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    @app.get("/api/health")
    def health() -> dict[str, str]:
        """Liveness probe used by CI, Docker and the hosting platform."""
        return {"status": "ok", "version": __version__, "provider": get_settings().llm_provider}

    @app.get("/api/catalog")
    def catalog() -> list[dict[str, object]]:
        return [
            {
                "category": e.category,
                "width": e.width,
                "depth": e.depth,
                "height": e.height,
                "freestanding": e.freestanding,
            }
            for e in CATALOG.values()
        ]

    @app.get("/api/examples")
    def examples() -> list[str]:
        return EXAMPLES

    @app.post("/api/generate")
    def generate(
        req: GenerateRequest, pipeline: Pipeline = Depends(get_pipeline)
    ) -> GenerationResult:
        try:
            return pipeline.run(
                req.prompt,
                room_width=req.room_width,
                room_depth=req.room_depth,
                max_iterations=req.max_iterations,
                with_fault=req.inject_fault,
            )
        except UnderstandingError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    directory = static_dir if static_dir is not None else get_settings().static_dir
    if directory and Path(directory).is_dir():
        # Mounted last so it never shadows the API routes.
        app.mount("/", StaticFiles(directory=directory, html=True), name="static")
    return app


app = create_app()
