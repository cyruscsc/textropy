"""`sentiment.document` — DistilBERT SST-2 scoring (spec §4).

Spec §4 lists the sentiment model as a Pass 1 extractor while §5 puts a `sentiment`
feature in `features/tier2/`. Both hold: the *model invocation* is a signal (so it runs
once per text no matter how many features read it) and the Tier 2 feature is the thin
computer that shapes it into the response payload.

Scoring is per sentence (spec §3.1 lists the required signal as `spacy.doc` (sentences)),
then aggregated to a document label.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models_ml import model_registry
from app.models_ml.sentiment_model import SentimentModel
from app.pipeline.context import AnalysisContext
from app.signals.base import SENTIMENT_DOCUMENT, SPACY_DOC, SignalExtractor

# Sentences are scored in batches to bound peak memory on long inputs.
_BATCH_SIZE = 16


@dataclass(frozen=True)
class SentenceSentiment:
    text: str
    label: str
    score: float


@dataclass(frozen=True)
class DocumentSentiment:
    label: str
    score: float
    per_sentence: list[SentenceSentiment]


class SentimentExtractor(SignalExtractor):
    name = SENTIMENT_DOCUMENT
    depends_on = (SPACY_DOC,)
    models = (model_registry.SENTIMENT,)

    def extract(self, ctx: AnalysisContext) -> DocumentSentiment:
        import torch

        doc = ctx.get(SPACY_DOC)
        sentiment: SentimentModel = model_registry.get_model(model_registry.SENTIMENT)

        sentences = [s.text.strip() for s in doc.sents if s.text.strip()]
        if not sentences:
            return DocumentSentiment(label="neutral", score=0.0, per_sentence=[])

        per_sentence: list[SentenceSentiment] = []
        for start in range(0, len(sentences), _BATCH_SIZE):
            batch = sentences[start : start + _BATCH_SIZE]
            encoded = sentiment.tokenizer(
                batch, return_tensors="pt", padding=True, truncation=True, max_length=512
            )
            with torch.no_grad():
                logits = sentiment.model(**encoded).logits
                probs = torch.softmax(logits.float(), dim=-1)

            for text, row in zip(batch, probs, strict=True):
                idx = int(row.argmax())
                per_sentence.append(
                    SentenceSentiment(
                        text=text,
                        label=sentiment.id2label.get(idx, str(idx)),
                        score=float(row[idx]),
                    )
                )

        # Document label: highest total confidence mass across sentences. Length-weighting
        # would over-count long sentences; equal weighting keeps the label interpretable.
        totals: dict[str, float] = {}
        for item in per_sentence:
            totals[item.label] = totals.get(item.label, 0.0) + item.score

        label = max(totals, key=lambda k: totals[k])
        matching = [s.score for s in per_sentence if s.label == label]
        return DocumentSentiment(
            label=label,
            score=sum(matching) / len(matching),
            per_sentence=per_sentence,
        )
