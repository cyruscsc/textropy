"""Tier 3 conditional surprisal (spec §3.2) — **asymmetric**.

Mean per-word surprisal (nats) of one text given the other as context. Uses the same
LM-to-spaCy alignment as the single-text Tier 3 feature, so "per word" means the same
thing in both, and reuses each text's `spacy.doc` rather than re-parsing.
"""

from __future__ import annotations

from typing import Any

from app.comparison.base import ComparisonComputer
from app.features.tier3.surprisal import word_surprisals
from app.pipeline.context import AnalysisContext
from app.signals.alignment import align_offsets, spacy_spans
from app.signals.base import SPACY_DOC
from app.signals.lm_extractor import score_continuation


def _mean_conditional_surprisal(context_text: str, target_doc: Any) -> float | None:
    scores = score_continuation(context_text, target_doc.text)
    if not scores.token_ids:
        return None

    alignment = align_offsets(spacy_spans(target_doc), scores.offsets)
    values = [value for _, value in word_surprisals(target_doc, scores, alignment)]
    if not values:
        return None
    return round(sum(values) / len(values), 4)


class ConditionalSurprisal(ComparisonComputer):
    name = "conditional_surprisal"
    tier = 3
    symmetric = False
    requires = (SPACY_DOC,)

    def compute(self, a: AnalysisContext, b: AnalysisContext) -> dict[str, Any]:
        return {
            "a_given_b": _mean_conditional_surprisal(b.text, a.get(SPACY_DOC)),
            "b_given_a": _mean_conditional_surprisal(a.text, b.get(SPACY_DOC)),
        }
