"""Pluggable multimodal LLM provider for the PCBA TPI Generation feature.

Mirrors ``app/services/llm_provider.py`` and ``app/services/vision_llm.py``:
a ``MultimodalLLMProvider`` ``Protocol`` (``describe_visual`` for circuit
diagrams / drawings and ``draft_section`` for narrative generation), a default
deterministic ``MockMultimodalProvider`` that runs with no network access or API
key (Req 8.1), and an ``OpenAIMultimodalProvider`` selected purely by
configuration — mirroring the existing ``AVIP_VISION_LLM`` / ``OPENAI_API_KEY``
/ ``OPENAI_MODEL`` env pattern (Req 8.2). ``get_multimodal_provider(config)``
performs the selection, defaulting to the mock and falling back to it (with a
logged warning) for an unknown provider.

No network call is made at import or construction time — the OpenAI client is
built lazily on first use (Req 8.3). Provider errors propagate to the caller so
the extraction/generation stage can flag the affected input for manual
annotation rather than fabricating content (Req 8.4, 2.4).

Task 1 provides this module docstring only; the Protocol and providers are
implemented in task 2.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.config import settings
from app.services.tpi_types import InputType

logger = logging.getLogger("app.tpi.llm_provider")


@runtime_checkable
class MultimodalLLMProvider(Protocol):
    """Provider interface for visual extraction + narrative drafting.

    Mirrors ``LLMProvider`` in ``app/services/llm_provider.py``: a ``name`` and
    async methods that the extraction (``describe_visual``, Req 2.2) and
    generation (``draft_section``, Req 3.x) stages call through. Implementations
    MUST NOT swallow provider errors into fabricated content — raising is
    acceptable and the caller flags the affected input for manual annotation
    (Req 8.4, 2.4).
    """

    name: str

    async def describe_visual(self, image_ref: str, kind: InputType) -> dict:
        """Return a structured description of a circuit diagram / drawing."""
        ...

    async def draft_section(self, section: str, context: dict) -> str:
        """Draft the narrative for a TPI section from mapped context."""
        ...


# Matches HTML comments, including multi-line ones (e.g. the fixture disclaimer
# header ``<!-- FIXTURE PENDING REAL CLIENT SAMPLES ... -->``). Dependency-free.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _clean_body(text: str) -> str:
    """Clean mapped content into readable prose for the drafted section body.

    Deterministic and dependency-free: strips HTML comments (the fixture
    disclaimer header, multi-line included) so they never reach the drafted
    body, and collapses runaway blank lines while preserving the procedure's own
    steps/lines. No randomness, no timestamps — the same input always yields the
    same output.
    """
    if not text:
        return ""
    cleaned = _HTML_COMMENT_RE.sub("", text)
    # Normalize line endings and trim trailing whitespace per line so the
    # procedure's real newlines display cleanly (frontend uses whitespace-pre-wrap).
    lines = [ln.rstrip() for ln in cleaned.replace("\r\n", "\n").split("\n")]
    # Collapse 3+ consecutive blank lines down to a single blank line.
    out: list[str] = []
    blank_run = 0
    for ln in lines:
        if ln.strip() == "":
            blank_run += 1
            if blank_run > 1:
                continue
            out.append("")
        else:
            blank_run = 0
            out.append(ln)
    return "\n".join(out).strip()


def _stable_digest(*parts: str) -> str:
    """Short, stable hex digest over the given parts.

    Used to make the mock's output deterministic — the same inputs always
    produce the same description/narrative, so tests are stable and the feature
    runs with no API key or network access (Req 8.1).
    """
    joined = "\u241f".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]


class MockMultimodalProvider:
    """Default provider (Req 8.1) — deterministic, no external dependency.

    ``describe_visual`` returns a stable structured dict derived purely from the
    ``image_ref`` and ``kind``; ``draft_section`` returns a stable narrative
    string built from the section name and its context. No network call is made
    for either, and identical inputs always yield identical output, which keeps
    tests stable and lets extraction/generation run with no API key.
    """

    name = "mock"

    async def describe_visual(self, image_ref: str, kind: InputType) -> dict:
        kind_value = kind.value if isinstance(kind, InputType) else str(kind)
        digest = _stable_digest("describe_visual", kind_value, image_ref)
        # Deterministic component list seeded from the digest so a given
        # image_ref always yields the same structured description.
        catalog = [
            "connector",
            "resistor",
            "capacitor",
            "ic_package",
            "test_point",
            "power_rail",
            "ground_plane",
            "trace",
        ]
        seed = int(digest, 16)
        count = 3 + (seed % 3)  # 3..5 components, stable per input
        components = [catalog[(seed >> (i * 3)) % len(catalog)] for i in range(count)]
        logger.info(
            "mock describe_visual kind=%s ref=%s digest=%s components=%d",
            kind_value,
            image_ref,
            digest,
            len(components),
        )
        return {
            "kind": kind_value,
            "image_ref": image_ref,
            "summary": (
                f"Structured description of the {kind_value.replace('_', ' ')}, "
                f"identifying its key components and test points."
            ),
            "components": components,
            "provider": self.name,
            "digest": digest,
        }

    async def draft_section(self, section: str, context: dict) -> str:
        # Compose a clean, readable, TPI-style narrative from the mapped content
        # this section was given. Fully deterministic (same inputs -> same
        # output, no network, no randomness) and free of any debug artifacts:
        # no "[Mock draft ...]" prefix, no context repr, no digest, no
        # len(context) leak. The body is the real cleaned mapped content so the
        # review workbench shows readable procedure prose (Req 8.1).
        title = str(context.get("title") or section or "Section").strip()
        mapped_content = context.get("mapped_content")
        body = _clean_body(mapped_content if isinstance(mapped_content, str) else "")

        logger.info(
            "mock draft_section section=%s title=%s body_chars=%d incomplete=%s",
            section,
            title,
            len(body),
            bool(context.get("incomplete")),
        )

        lead = f"{title}. The following was compiled from the source procedures."
        # Honest, short marker that this draft came from the mock provider.
        note = (
            "(Draft generated by the mock provider; pending real LLM/client "
            "template.)"
        )
        if body:
            return f"{lead}\n\n{body}\n\n{note}"
        return f"{lead}\n\n{note}"


class OpenAIMultimodalProvider:
    """Real multimodal provider backed by OpenAI, selected via configuration
    (Req 8.2).

    Mirrors ``OpenAILLMProvider`` (``llm_provider.py``) and the ``vision_llm``
    service: the OpenAI client is constructed *lazily* on first use, never at
    import or construction time, so selecting this provider makes no network
    call and importing this module has no external dependency (Req 8.3).

    ``describe_visual`` base64-encodes the image at ``image_ref`` (reusing the
    ``vision_llm`` approach) and sends it as an ``image_url`` content block to
    ``chat.completions``, then parses the JSON reply into a ``dict``.
    ``draft_section`` is a text-only completion that returns the drafted
    narrative. On any provider/transport error, or a malformed JSON reply, the
    exception PROPAGATES to the caller rather than being swallowed into
    fabricated content — the extraction/generation stage then flags the affected
    input for manual annotation (Req 8.4, 2.4).
    """

    name = "openai"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        # Mirror the OPENAI_API_KEY / OPENAI_MODEL config pattern from config.py.
        self._api_key = api_key if api_key is not None else settings.openai_api_key
        self._model = model or settings.openai_model
        self._client = None  # constructed lazily; no network at construction (Req 8.3)

    def _ensure_client(self):
        """Lazily construct the OpenAI client (no network call here)."""
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise RuntimeError(
                "OpenAIMultimodalProvider: no OPENAI_API_KEY configured"
            )
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "OpenAIMultimodalProvider: the 'openai' package is not installed"
            ) from exc
        self._client = OpenAI(api_key=self._api_key)
        return self._client

    @staticmethod
    def _encode_image(image_ref: str) -> str:
        """Encode the file at ``image_ref`` to base64 (mirrors ``vision_llm``).

        Errors (missing file, unreadable path) propagate rather than being
        swallowed — the caller flags the affected input for manual annotation
        (Req 8.4, 2.4).
        """
        return base64.b64encode(Path(image_ref).read_bytes()).decode()

    async def describe_visual(self, image_ref: str, kind: InputType) -> dict:
        """Extract a structured description of a circuit diagram / drawing.

        Base64-encodes the image at ``image_ref`` and sends it as an
        ``image_url`` content block alongside a system prompt describing the
        extraction task, then parses the JSON reply into a ``dict``. Errors
        (auth, transport, malformed JSON) PROPAGATE (Req 8.4).
        """
        client = self._ensure_client()
        kind_value = kind.value if isinstance(kind, InputType) else str(kind)
        # Encode first — a bad image_ref surfaces here and propagates.
        img_b64 = self._encode_image(image_ref)

        system_prompt = (
            "You are an expert electronics test engineer extracting structured "
            "content from a circuit diagram or engineering drawing so a Test "
            "Procedure Instruction (TPI) can be generated from it. Examine the "
            "image and identify the components, nets/test points, and any "
            "annotations relevant to testing. Respond ONLY with valid JSON in "
            "this exact shape: {\"kind\": \"<input kind>\", \"summary\": "
            "\"<one-paragraph description of the diagram/drawing>\", "
            "\"components\": [\"<component or test point>\", ...], "
            "\"notes\": \"<any testing-relevant annotations, or empty string>\"}."
        )
        user_content = [
            {
                "type": "text",
                "text": (
                    f"This is a {kind_value}. Extract a structured description "
                    "for TPI generation as specified."
                ),
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_b64}",
                    "detail": "high",
                },
            },
        ]
        # Errors here (auth, rate limit, transport) propagate to the caller.
        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_tokens=800,
            temperature=0.0,  # low temp for deterministic extraction
        )
        text = (response.choices[0].message.content or "").strip()
        data = self._parse_json(text)  # raises on malformed provider output
        # Carry the request context through for provenance/debugging.
        data.setdefault("kind", kind_value)
        data.setdefault("image_ref", image_ref)
        data["provider"] = self.name
        return data

    async def draft_section(self, section: str, context: dict) -> str:
        """Draft the narrative for a TPI section from mapped ``context``.

        Text-only completion; returns the drafted text. Errors propagate
        (Req 8.4).
        """
        client = self._ensure_client()
        context_repr = "; ".join(
            f"{key}={context[key]!r}" for key in sorted(context)
        )
        system_prompt = (
            "You are an expert test engineer drafting a section of a Test "
            "Procedure Instruction (TPI) for a printed circuit board assembly. "
            "Write clear, concise, professional narrative for the requested "
            "section using ONLY the provided context — do not invent test steps, "
            "results, or equipment that the context does not support. Respond "
            "with the section narrative as plain text, no preamble."
        )
        user_prompt = (
            f"TPI section: {section}\n\n"
            f"Context ({len(context)} item(s)): {context_repr or 'none'}"
        )
        # Errors here (auth, rate limit, transport) propagate to the caller.
        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=800,
            temperature=0.1,  # low temp for near-deterministic drafting
        )
        return (response.choices[0].message.content or "").strip()

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Parse the model's JSON reply into a ``dict``.

        A malformed reply is a provider error: raise rather than fabricate
        content (Req 8.4). Strips markdown code fences the way ``vision_llm`` /
        ``OpenAILLMProvider`` do before decoding.
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
        if not isinstance(data, dict):
            raise ValueError(
                "OpenAIMultimodalProvider: expected a JSON object from the model"
            )
        return data


def _select_multimodal_provider(name: str | None) -> MultimodalLLMProvider:
    """Core selection logic shared by the two public selectors.

    ``name`` is a provider name string (``"mock"`` / ``"openai"`` or ``None``).
    ``None`` / empty / unknown falls back to the deterministic mock (with a
    logged warning for a genuinely unknown value), so selection never fails.
    ``OpenAIMultimodalProvider`` is constructed lazily (its client is only built
    on first use), so selecting ``"openai"`` makes no network call here (Req 8.3).
    """
    selected = (name or "mock").strip().lower()

    if selected == "mock":
        logger.info(
            "Selected multimodal provider 'mock' (default, no external dependency)"
        )
        return MockMultimodalProvider()

    if selected == "openai":
        logger.info(
            "Selected multimodal provider 'openai' (model=%s, api_key_configured=%s)",
            settings.openai_model,
            bool(settings.openai_api_key),
        )
        # No network at construction — the OpenAI client is built lazily on
        # first use (Req 8.3). If OPENAI_API_KEY is missing, _ensure_client
        # raises RuntimeError on first use, which the endpoint maps to 400.
        return OpenAIMultimodalProvider()

    logger.warning(
        "Unknown multimodal provider '%s'; falling back to mock provider", selected
    )
    return MockMultimodalProvider()


def get_multimodal_provider(config) -> MultimodalLLMProvider:
    """Select the multimodal provider from a config/settings object (Req 8.1-8.3).

    Reads the provider name from ``config.llm_provider`` first (kept for
    backward compatibility with callers/tests that set it), then falls back to
    ``config.tpi_llm_provider`` — the setting on the application ``settings``
    object (``AVIP_TPI_LLM_PROVIDER``) — then to ``"mock"``. So passing
    ``settings`` now selects based on ``AVIP_TPI_LLM_PROVIDER`` instead of
    always defaulting to the mock. ``"mock"`` (the default) returns the
    deterministic, dependency-free mock; ``"openai"`` returns the
    lazily-constructed ``OpenAIMultimodalProvider`` (no network at selection
    time, Req 8.3); an unknown value falls back to the mock with a logged
    warning.
    """
    name = (
        getattr(config, "llm_provider", None)
        or getattr(config, "tpi_llm_provider", None)
        or "mock"
    )
    return _select_multimodal_provider(name)


def get_multimodal_provider_by_name(name: str | None) -> MultimodalLLMProvider:
    """Select the multimodal provider by an explicit name string (Req 8.1-8.3).

    Convenience for a per-request override: ``"mock"`` / ``"openai"`` select
    that provider directly; ``None`` (no override supplied) falls back to the
    configured default from ``settings`` via :func:`get_multimodal_provider`.
    Reuses the same selection logic — no network call at selection time (Req 8.3).
    """
    if name is None:
        return get_multimodal_provider(settings)
    return _select_multimodal_provider(name)
