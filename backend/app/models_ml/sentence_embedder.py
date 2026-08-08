"""Sentence embedding singleton (`all-MiniLM-L6-v2`)."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings


def load() -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_settings().sentence_embedder_model)
