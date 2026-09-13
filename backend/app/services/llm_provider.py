"""Pluggable LLM provider interface for free-text field comparison (Req 5).

The comparison service uses an ``LLMProvider`` *only* for free-text fields
(Req 5.1). The default is a ``MockLLMProvider`` that runs with no external
dependency so the feature works out of the box (Req 5.2). A real provider
(``OpenAILLMProvider``) can be selected purely through configuration, with no
code change to swap (Req 5.3, 8.4) — its selection mirrors the existing
``AVIP_VISION_LLM`` / ``OPENAI_API_KEY`` / ``OPENAI_MODEL`` env pattern from
``app/config.py``.

Errors are surfaced cleanly rather than swallowed into a false "agree": the
comparison service (task 4.2) catches provider failures and routes the affected
field to manual review with provenance ``llm-unavailable`` (Req 5.5). Nothing
here makes a network call at import or construction time — the OpenAI client is
built lazily on first use.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from app.config import settings
from app.services.sc_config import ComparisonConfig

logger = logging.getLogger("app.source_comparison.llm_provider")


class LLMComparison(BaseModel):
    """Structured result of a free-text comparison (design: LLMComparison shape).

    ``differ`` is the judgement (do the two values disagree?) and ``rationale``
    is a short human-readable explanation carried through to the review gate.
    """

    differ: bool
    rationale: str


@runtime_checkable
class LLMProvider(Protocol):
    """Provider interface used only for free-text field comparison (Req 5.1)."""

    name: str

    async def compare_text(self, a: str | None, b: str | None) -> LLMComparison:
        """Compare two free-text values and return a structured judgement.

        Implementations MUST NOT swallow provider errors into a false "agree";
        raising is acceptable and the comparison service will route the field to
        manual review (Req 5.5).
        """
        ...


def _normalize(value: str | None) -> str:
    """Trim + casefold a free-text value for deterministic comparison.

    ``None`` is treated as an empty string so a present/absent pair is handled
    consistently rather than raising.
    """
    if value is None:
        return ""
    return " ".join(str(value).split()).casefold()


class MockLLMProvider:
    """Default provider (Req 5.2) — deterministic, no external dependency.

    Judgement heuristic: two values *differ* when their trimmed, case-folded,
    whitespace-collapsed forms are not equal. This is deterministic (same inputs
    always yield the same result), which keeps tests stable and lets the feature
    run with no API key or network access.
    """

    name = "mock"

    async def compare_text(self, a: str | None, b: str | None) -> LLMComparison:
        na, nb = _normalize(a), _normalize(b)
        differ = na != nb
        if differ:
            rationale = (
                "Mock provider: normalized free-text values are not equivalent "
                f"({a!r} vs {b!r})."
            )
        else:
            rationale = (
                "Mock provider: free-text values are equivalent after trimming "
                "and case-folding."
            )
        logger.info(
            "mock compare_text differ=%s a_len=%d b_len=%d",
            differ,
            len(na),
            len(nb),
        )
        return LLMComparison(differ=differ, rationale=rationale)


class OpenAILLMProvider:
    """Real provider backed by OpenAI, selected via configuration (Req 5.3).

    Mirrors the existing ``vision_llm`` service pattern: the client is created
    *lazily* on first use, never at import or construction time, so selecting
    this provider makes no network call and importing the module has no external
    dependency. On any provider/transport error, ``compare_text`` propagates the
    exception rather than returning a false "agree" — the comparison service
    catches it and routes the field to manual review (Req 5.5).
    """

    name = "openai"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        # Mirror the OPENAI_API_KEY / OPENAI_MODEL config pattern from config.py.
        self._api_key = api_key if api_key is not None else settings.openai_api_key
        self._model = model or settings.openai_model
        self._client = None  # constructed lazily; no network at construction

    def _ensure_client(self):
        """Lazily construct the OpenAI client (no network call here)."""
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise RuntimeError("OpenAILLMProvider: no OPENAI_API_KEY configured")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "OpenAILLMProvider: the 'openai' package is not installed"
            ) from exc
        self._client = OpenAI(api_key=self._api_key)
        return self._client

    async def compare_text(self, a: str | None, b: str | None) -> LLMComparison:
        client = self._ensure_client()
        prompt = (
            "You compare two free-text inspection notes and decide whether they "
            "disagree in substance (not just wording). Respond ONLY with JSON: "
            '{"differ": <true|false>, "rationale": "<one sentence>"}.\n\n'
            f"VALUE A: {a!r}\nVALUE B: {b!r}"
        )
        # Errors here (auth, rate limit, transport) propagate to the caller.
        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a meticulous semiconductor quality reviewer "
                        "comparing free-text inspection notes."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=200,
            temperature=0.0,
        )
        text = (response.choices[0].message.content or "").strip()
        return self._parse(text)

    @staticmethod
    def _parse(text: str) -> LLMComparison:
        """Parse the model's JSON reply into an ``LLMComparison``.

        A malformed reply is a provider error: raise rather than guess "agree".
        """
        import json

        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
        data = json.loads(cleaned)  # raises on malformed provider output
        return LLMComparison(
            differ=bool(data["differ"]),
            rationale=str(data.get("rationale", "")),
        )


def get_llm_provider(config: ComparisonConfig) -> LLMProvider:
    """Select the LLM provider from configuration (Req 5.2, 5.3, 8.4).

    ``config.llm_provider`` chooses the implementation with no code change to
    swap. ``"mock"`` (the default) returns the dependency-free mock. ``"openai"``
    returns a lazily-constructed ``OpenAILLMProvider`` — no network call is made
    here. An unknown or misconfigured provider name falls back to the mock with a
    logged warning rather than failing, so free-text comparison always has a
    working provider.
    """
    selected = (config.llm_provider or "mock").strip().lower()

    if selected == "mock":
        logger.info("Selected LLM provider 'mock' (default, no external dependency)")
        return MockLLMProvider()

    if selected == "openai":
        logger.info(
            "Selected LLM provider 'openai' (model=%s, api_key_configured=%s)",
            settings.openai_model,
            bool(settings.openai_api_key),
        )
        return OpenAILLMProvider()

    logger.warning(
        "Unknown LLM provider '%s'; falling back to mock provider", selected
    )
    return MockLLMProvider()
