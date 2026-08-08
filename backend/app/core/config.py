"""Application settings.

All values are overridable via environment variables prefixed with ``TEXTROPY_``
(e.g. ``TEXTROPY_MODEL_LOADING=lazy``).
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TEXTROPY_",
        env_file=".env",
        extra="ignore",
        protected_namespaces=(),
    )

    app_name: str = "Textropy API"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Model loading (spec §4) -------------------------------------------------
    # "eager": load every model in `eager_tiers` during startup, so /health readiness
    #   flips to ready only once they are resident.
    # "lazy": load each model on first use. Lower startup RAM on constrained hosts,
    #   at the cost of a slow first request per tier.
    model_loading: Literal["eager", "lazy"] = "eager"

    # Which tiers to preload when model_loading == "eager". Tier 1 is spaCy only
    # (~200MB); adding 2 and 3 brings resident memory to ~1.5-2GB.
    eager_tiers: list[int] = [1]

    # --- Model identifiers -------------------------------------------------------
    spacy_model: str = "en_core_web_sm"
    causal_lm_model: str = "distilgpt2"
    sentence_embedder_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    sentiment_model: str = "distilbert-base-uncased-finetuned-sst-2-english"
    coref_model: str = "biu-nlp/f-coref"

    # --- Request limits ----------------------------------------------------------
    # Spec §9 records "no input length cap enforced yet" as an accepted MVP trade-off.
    # The hook exists here so the deferred fix is a config change, not a code change.
    # 0 disables the check.
    max_text_chars: int = 0

    # Torch intra-op threads; 0 leaves the torch default in place.
    torch_num_threads: int = 0


_settings: Settings | None = None


def get_settings() -> Settings:
    """Process-wide settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
