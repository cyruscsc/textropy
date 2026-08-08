"""Causal LM singleton (DistilGPT2) used for perplexity / surprisal (spec §3, Tier 3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings


@dataclass(frozen=True)
class CausalLM:
    """Tokenizer + model pair, plus the context window we may feed it."""

    tokenizer: Any
    model: Any
    max_length: int

    def context_window(self) -> int:
        return self.max_length


def load() -> CausalLM:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    settings = get_settings()
    if settings.torch_num_threads > 0:
        torch.set_num_threads(settings.torch_num_threads)

    name = settings.causal_lm_model
    tokenizer = AutoTokenizer.from_pretrained(name)
    model = AutoModelForCausalLM.from_pretrained(name)
    model.eval()

    max_length = getattr(model.config, "n_positions", None) or getattr(
        model.config, "max_position_embeddings", 1024
    )
    return CausalLM(tokenizer=tokenizer, model=model, max_length=int(max_length))
