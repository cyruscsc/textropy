"""Sentiment classifier singleton (DistilBERT SST-2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings


@dataclass(frozen=True)
class SentimentModel:
    tokenizer: Any
    model: Any
    id2label: dict[int, str]


def load() -> SentimentModel:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    name = get_settings().sentiment_model
    tokenizer = AutoTokenizer.from_pretrained(name)
    model = AutoModelForSequenceClassification.from_pretrained(name)
    model.eval()

    id2label = {int(k): str(v).lower() for k, v in model.config.id2label.items()}
    return SentimentModel(tokenizer=tokenizer, model=model, id2label=id2label)
