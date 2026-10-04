from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from spatialmind.agents.construction import construct_scene
from spatialmind.agents.llm import MockProvider
from spatialmind.agents.planner import plan
from spatialmind.agents.understanding import UnderstandingError
from spatialmind.controller.pipeline import Pipeline, Stage, inject_fault
from spatialmind.main import EXAMPLES, create_app, get_pipeline
from spatialmind.schemas import ObjectRequest, SceneSpec

PROPOSAL_EXAMPLE = EXAMPLES[0]


@pytest.fixture
def pipeline() -> Pipeline:
    return Pipeline(MockProvider())


def test_proposal_example_end_to_end(pipeline: Pipeline) -> None:
    result = pipeline.run(PROPOSAL_EXAMPLE)
    assert result.passed
    assert result.iterations == 0 and not result.refined
    stages = [s.stage for s in result.trace]
    assert stages == [Stage.UNDERSTAND, Stage.PLAN, Stage.CONSTRUCT, Stage.VERIFY, Stage.DONE]
    assert result.final_report.metrics["constraint_satisfaction"] == 1.0
    assert {o["category"] for o in result.scene["objects"]} == {"bed", "desk", "wardrobe"}


def test_all_examples_produce_valid_scenes(pipeline: Pipeline) -> None:
    for prompt in EXAMPLES:
        result = pipeline.run(prompt)
        assert result.passed, (prompt, [v.message for v in result.final_report.violations])


def test_injected_fault_is_detected_and_repaired(pipeline: Pipeline) -> None:
    result = pipeline.run(PROPOSAL_EXAMPLE, with_fault=True)
    assert result.fault_injected is not None
    assert not result.initial_report.passed
    assert result.initial_report.metrics["collisions"] >= 1
    assert result.passed and result.refined
    assert result.iterations >= 1
    stages = [s.stage for s in result.trace]
    assert Stage.INJECT_FAULT in stages and Stage.REPLAN in stages


def test_without_refinement_the_fault_remains(pipeline: Pipeline) -> None:
    """Baseline for the evaluation: single pass (no refinement loop) cannot recover."""
    result = pipeline.run(PROPOSAL_EXAMPLE, with_fault=True, max_iterations=0)
    assert not result.passed and result.iterations == 0 and not result.refined


def test_room_dimensions_override(pipeline: Pipeline) -> None:
    result = pipeline.run(PROPOSAL_EXAMPLE, room_width=5.0, room_depth=4.5)
    assert result.scene["room"]["width"] == 5.0 and result.scene["room"]["depth"] == 4.5
    assert result.passed


def test_unsolvable_request_stops_after_budget(pipeline: Pipeline) -> None:
    result = pipeline.run("a tiny office with four sofas and a bed", max_iterations=2)
    assert not result.passed
    assert result.iterations <= 2
    assert result.trace[-1].stage == Stage.DONE and result.trace[-1].passed is False


def test_understanding_failure_propagates(pipeline: Pipeline) -> None:
    with pytest.raises(UnderstandingError):
        pipeline.run("something nice")


def test_inject_fault_needs_two_objects() -> None:
    memory = plan(SceneSpec(objects=[ObjectRequest(category="bed")]))
    assert inject_fault(memory) is None


def test_construct_scene_payload_is_blender_ready() -> None:
    memory = plan(SceneSpec(objects=[ObjectRequest(category="bed")]))
    scene = construct_scene(memory)
    assert scene["format"] == "spatialmind.scene/v1"
    obj = scene["objects"][0]
    assert obj["asset"] == "placeholder/bed"
    assert len(obj["location"]) == 3 and obj["location"][2] == 0.0
    assert obj["dimensions"] == [1.6, 2.0, 0.6]
    assert scene["room"]["openings"]


# -- HTTP API ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    app = create_app(static_dir="")
    app.dependency_overrides[get_pipeline] = lambda: Pipeline(MockProvider())
    return TestClient(app)


def test_health_endpoints(client: TestClient) -> None:
    for path in ("/health", "/api/health"):
        body = client.get(path).json()
        assert body["status"] == "ok" and "version" in body


def test_catalog_and_examples(client: TestClient) -> None:
    cats = {c["category"] for c in client.get("/api/catalog").json()}
    assert {"bed", "desk", "wardrobe"} <= cats
    assert client.get("/api/examples").json() == EXAMPLES


def test_generate_endpoint(client: TestClient) -> None:
    response = client.post("/api/generate", json={"prompt": PROPOSAL_EXAMPLE})
    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is True
    assert body["spec"]["room_type"] == "bedroom"
    assert len(body["scene"]["objects"]) == 3


def test_generate_with_fault_injection(client: TestClient) -> None:
    body = client.post(
        "/api/generate", json={"prompt": PROPOSAL_EXAMPLE, "inject_fault": True}
    ).json()
    assert body["refined"] is True and body["fault_injected"]


def test_generate_validation_errors(client: TestClient) -> None:
    assert client.post("/api/generate", json={"prompt": "ab"}).status_code == 422
    assert client.post("/api/generate", json={"prompt": "a nice room"}).status_code == 422
    bad = {"prompt": PROPOSAL_EXAMPLE, "room_width": 100}
    assert client.post("/api/generate", json=bad).status_code == 422


def test_static_frontend_is_served_without_shadowing_api(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html>SpatialMind UI</html>")
    app = create_app(static_dir=str(tmp_path))
    client = TestClient(app)
    assert "SpatialMind UI" in client.get("/").text
    assert client.get("/api/health").json()["status"] == "ok"
