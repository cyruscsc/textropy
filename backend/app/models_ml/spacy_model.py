"""spaCy pipeline singleton (`en_core_web_sm`)."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings


def load() -> Any:
    import spacy

    name = get_settings().spacy_model
    try:
        return spacy.load(name)
    except OSError as exc:
        raise RuntimeError(
            f"spaCy model {name!r} is not installed. It is declared as a project "
            f"dependency; run `uv sync` (or `uv run python -m spacy download {name}`)."
        ) from exc
