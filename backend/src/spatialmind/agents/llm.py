"""LLM providers for the Scene Understanding agent.

A provider turns (system instructions, user prompt) into raw JSON text. Keeping the provider
behind a tiny interface means the agent, the CI pipeline and the tests never depend on a
specific vendor: ``MockProvider`` is a deterministic rule-based parser, ``GeminiProvider``
calls Google's Gemini API.
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from spatialmind.catalog import CATALOG, normalize_category
from spatialmind.config import Settings


class LLMProvider(Protocol):
    name: str

    def generate_json(self, system: str, prompt: str) -> str: ...


# -- Gemini ---------------------------------------------------------------------------


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", client: Any = None) -> None:
        self._api_key = api_key
        self.model = model
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def generate_json(self, system: str, prompt: str) -> str:
        from google.genai import types

        response = self._get_client().models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        return str(response.text)


# -- Deterministic mock ---------------------------------------------------------------

_NUMBER_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4}
_NEAR_WORDS = r"\b(?:near|next to|close to|beside|by)\b"
_AWAY_WORDS = r"\b(?:away from|far from|far away from)\b"
_WALL_WORDS = r"against (?:the |a )?(?:(north|south|east|west) )?wall"
_STYLE_WORDS = ("modern", "minimalist", "cozy", "rustic", "industrial", "classic", "scandinavian")
_NAMES = sorted(
    {n for e in CATALOG.values() for n in (e.category.replace("_", " "), e.category, *e.synonyms)},
    key=len,
    reverse=True,
)
_NAME_RE = re.compile(r"\b(" + "|".join(re.escape(n) for n in _NAMES) + r")s?\b")
_OPENING_RE = re.compile(r"\b(window|door)s?\b")


class MockProvider:
    """Rule-based text -> scene-spec JSON. Deterministic stand-in for an LLM."""

    name = "mock"

    def generate_json(self, system: str, prompt: str) -> str:
        return json.dumps(self.parse(prompt))

    # Mentions are (position, kind, value) where kind is "object" or "opening".
    @staticmethod
    def _mentions(text: str) -> list[tuple[int, str, str]]:
        found: list[tuple[int, str, str]] = []
        taken: list[tuple[int, int]] = []
        for m in _NAME_RE.finditer(text):
            category = normalize_category(m.group(1))
            if category:
                found.append((m.start(), "object", category))
                taken.append((m.start(), m.end()))
        for m in _OPENING_RE.finditer(text):
            if not any(s <= m.start() < e for s, e in taken):
                found.append((m.start(), "opening", m.group(1)))
        return sorted(found)

    @staticmethod
    def _quantity(text: str, pos: int) -> int:
        words = re.findall(r"[a-z0-9]+", text[max(0, pos - 14) : pos])
        for word in reversed(words[-2:]):
            if word.isdigit():
                return max(1, min(int(word), 4))
            if word in _NUMBER_WORDS:
                return _NUMBER_WORDS[word]
        return 1

    def parse(self, prompt: str) -> dict[str, Any]:
        text = prompt.lower()
        if re.search(r"living|lounge|sitting", text):
            room_type = "living_room"
        elif re.search(r"office|study|workspace", text):
            room_type = "office"
        else:
            room_type = "bedroom"

        mentions = self._mentions(text)
        quantities: dict[str, int] = {}
        for pos, kind, value in mentions:
            if kind == "object":
                quantities[value] = max(quantities.get(value, 0), self._quantity(text, pos))
        objects = [{"category": c, "quantity": q} for c, q in quantities.items()]

        constraints: list[dict[str, Any]] = []
        last_subject: str | None = None
        spans: list[tuple[int, int]] = []
        start = 0
        for sep in re.finditer(r"[.;,]|\bbut\b", text):
            spans.append((start, sep.start()))
            start = sep.end()
        spans.append((start, len(text)))

        for lo, hi in spans:
            clause = text[lo:hi]
            local = [(p - lo, k, v) for p, k, v in mentions if lo <= p < hi]
            clause_objects = [m for m in local if m[1] == "object"]
            clause_subject: str | None = None

            for pattern, ctype in ((_AWAY_WORDS, "AWAY_FROM"), (_NEAR_WORDS, "NEAR")):
                for m in re.finditer(pattern, clause):
                    subject = _subject_before(clause_objects, m.start(), last_subject)
                    target = _target_after(local, m.end(), subject) if subject else None
                    if subject and target:
                        constraints.append({"type": ctype, "subject": subject, "target": target})
                        clause_subject = subject
            for m in re.finditer(_WALL_WORDS, clause):
                subject = _subject_before(clause_objects, m.start(), last_subject)
                if subject:
                    entry: dict[str, Any] = {"type": "AGAINST_WALL", "subject": subject}
                    if m.group(1):
                        entry["wall"] = m.group(1)
                    constraints.append(entry)
                    clause_subject = subject
            if clause_subject:
                last_subject = clause_subject
            elif clause_objects:
                last_subject = clause_objects[-1][2]

        if re.search(r"(enough|plenty of|sufficient) (space|room)|clearance|move around", text):
            for category in ("bed", "wardrobe", "desk"):
                if category in quantities:
                    constraints.append({"type": "CLEARANCE", "subject": category, "distance": 0.8})

        style = next((w for w in _STYLE_WORDS if w in text), None)
        return {
            "room_type": room_type,
            "objects": objects,
            "constraints": _dedupe(constraints),
            "style": style,
        }


Mention = tuple[int, str, str]


def _subject_before(objects: list[Mention], pos: int, fallback: str | None) -> str | None:
    """Last object mentioned before ``pos`` in the clause; a pronoun falls back to ``fallback``."""
    before = [m for m in objects if m[0] < pos]
    return before[-1][2] if before else fallback


def _target_after(mentions: list[Mention], pos: int, subject: str) -> str | None:
    after = [m for m in mentions if m[0] >= pos and m[2] != subject]
    return after[0][2] if after else None


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def build_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("LLM_PROVIDER=gemini requires GEMINI_API_KEY")
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    return MockProvider()
