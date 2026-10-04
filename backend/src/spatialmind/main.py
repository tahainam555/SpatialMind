"""FastAPI application entrypoint."""

from fastapi import FastAPI

from spatialmind import __version__

app = FastAPI(title="SpatialMind API", version=__version__)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe used by CI, Docker and the hosting platform."""
    return {"status": "ok", "version": __version__}
