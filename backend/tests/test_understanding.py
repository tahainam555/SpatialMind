import json
from types import SimpleNamespace
from typing import Any

import pytest

from spatialmind.agents.llm import GeminiProvider, MockProvider, build_provider
from spatialmind.agents.understanding import (
    UnderstandingAgent,
    UnderstandingError,
    build_system_prompt,
    resize_room,
)
from spatialmind.config import Settings
from spatialmind.schemas import ConstraintType, RoomType, default_room

EXAMPLE = (
    "Create a bedroom with a bed, desk and wardrobe, with the desk near the window "
    "and enough space for movement."
)


class Scripted:
    """Provider returning canned responses in order."""

    name = "scripted"

    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def generate_json(self, system: str, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.responses.pop(0)


def test_mock_parses_the_proposal_example() -> None:
    spec = UnderstandingAgent(MockProvider()).understand(EXAMPLE)
    assert spec.room_type == RoomType.BEDROOM
    assert {o.category for o in spec.objects} == {"bed", "desk", "wardrobe"}
    described = [c.describe() for c in spec.constraints]
    assert "NEAR(desk, window)" in described
    assert any(c.type == ConstraintType.CLEARANCE for c in spec.constraints)


def test_mock_handles_pronouns_quantities_and_walls() -> None:
    text = (
        "A modern study with two chairs and a desk near the door, keep it away from the "
        "bookshelf. Put the bookshelf against the east wall."
    )
    spec = UnderstandingAgent(MockProvider()).understand(text)
    assert spec.room_type == RoomType.OFFICE
    assert spec.style == "modern"
    qty = {o.category: o.quantity for o in spec.objects}
    assert qty["chair"] == 2 and qty["desk"] == 1
    described = [c.describe() for c in spec.constraints]
    assert "NEAR(desk, door)" in described
    assert "AWAY_FROM(desk, bookshelf)" in described
    assert "AGAINST_WALL(bookshelf, east)" in described


def test_mock_detects_living_room_and_synonyms() -> None:
    spec = UnderstandingAgent(MockProvider()).understand(
        "living room with a couch, a coffee table and a tv"
    )
    assert spec.room_type == RoomType.LIVING_ROOM
    assert {o.category for o in spec.objects} == {"sofa", "coffee_table", "tv_stand"}


def test_no_furniture_raises_understanding_error() -> None:
    agent = UnderstandingAgent(MockProvider(), max_retries=1)
    with pytest.raises(UnderstandingError):
        agent.understand("make it nice please")
    with pytest.raises(UnderstandingError):
        agent.understand("   ")


def test_agent_retries_with_error_feedback_then_succeeds() -> None:
    good = json.dumps({"room_type": "bedroom", "objects": [{"category": "bed"}]})
    provider = Scripted("not json at all", json.dumps({"objects": [{"category": "jetpack"}]}), good)
    spec = UnderstandingAgent(provider).understand("a bed")
    assert spec.objects[0].category == "bed"
    assert len(provider.prompts) == 3
    assert "previous answer was invalid" in provider.prompts[1]


def test_agent_accepts_markdown_fenced_json_and_rejects_non_object() -> None:
    fenced = '```json\n{"objects": [{"category": "desk"}]}\n```'
    assert UnderstandingAgent(Scripted(fenced)).understand("desk").objects[0].category == "desk"
    with pytest.raises(UnderstandingError):
        UnderstandingAgent(Scripted("[1, 2]"), max_retries=0).understand("desk")


def test_agent_applies_user_room_dimensions() -> None:
    spec = UnderstandingAgent(MockProvider()).understand(EXAMPLE, room_width=5.5, room_depth=4.2)
    room = spec.resolved_room
    assert (room.width, room.depth) == (5.5, 4.2)
    assert len(room.openings) == 2


def test_resize_room_keeps_openings_inside_smaller_walls() -> None:
    small = resize_room(default_room(RoomType.BEDROOM), 2.5, 2.5)
    for op in small.openings:
        half = op.width / 2
        assert half <= op.offset <= small.wall_length(op.wall) - half


def test_system_prompt_lists_catalog_and_constraint_types() -> None:
    prompt = build_system_prompt()
    assert "wardrobe" in prompt and "AGAINST_WALL" in prompt and "CLEARANCE" in prompt


def test_gemini_provider_uses_injected_client() -> None:
    calls: dict[str, Any] = {}

    def generate_content(**kwargs: Any) -> SimpleNamespace:
        calls.update(kwargs)
        return SimpleNamespace(text='{"objects": [{"category": "bed"}]}')

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    provider = GeminiProvider("key", "test-model", client=client)
    assert json.loads(provider.generate_json("sys", "a bed"))["objects"]
    assert calls["model"] == "test-model" and calls["contents"] == "a bed"
    assert calls["config"].response_mime_type == "application/json"


class Exploding:
    name = "exploding"

    def generate_json(self, system: str, prompt: str) -> str:
        raise ConnectionError("quota exceeded")


def test_provider_failure_becomes_understanding_error() -> None:
    with pytest.raises(UnderstandingError, match="quota exceeded"):
        UnderstandingAgent(Exploding()).understand("a bed")


def test_build_provider_selection() -> None:
    assert isinstance(build_provider(Settings(llm_provider="mock")), MockProvider)
    gemini = build_provider(Settings(llm_provider="gemini", gemini_api_key="abc"))
    assert isinstance(gemini, GeminiProvider)
    with pytest.raises(RuntimeError):
        build_provider(Settings(llm_provider="gemini", gemini_api_key=""))
