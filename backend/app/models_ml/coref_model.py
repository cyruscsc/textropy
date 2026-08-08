"""Coreference resolver singleton (fastcoref).

fastcoref is an *optional* extra (`uv sync --extra coref`): it is the least actively
maintained dependency in the stack and pins older transformers/spaCy ranges. When it is
absent or fails to load, the registry marks it unavailable and only the Tier 2
`coreference` feature degrades — the rest of the API is unaffected.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings


def load() -> Any:
    try:
        from fastcoref import FCoref
    except ImportError as exc:
        raise RuntimeError(
            "fastcoref is not installed. Install the optional extra with "
            "`uv sync --extra coref` to enable the Tier 2 coreference feature."
        ) from exc

    return FCoref(model_name_or_path=get_settings().coref_model, device="cpu")
