"""Tier 3 surprisal (spec §3.1).

Reported **per spaCy token**, not per BPE subword: the alignment signal maps each word to
the subwords composing it and their surprisals are summed. Values are in **nats**, so they
stay consistent with perplexity (`perplexity == exp(mean_subword_surprisal)`).
"""

from __future__ import annotations

from app.features.base import FeatureComputer
from app.pipeline.context import AnalysisContext
from app.signals.alignment import LmToSpacyAlignment
from app.signals.base import ALIGNMENT_LM_TO_SPACY, LM_TOKEN_LOGPROBS, SPACY_DOC
from app.signals.lm_extractor import TokenLogProbs


def word_surprisals(
    doc,
    logprobs: TokenLogProbs,
    alignment: LmToSpacyAlignment,
) -> list[tuple[str, float]]:
    """Surprisal in nats for each word token that has at least one scored subword.

    Words whose subwords are all unscored are skipped: the very first token of a text has
    no conditioning context, so attributing a surprisal to it would be fabricating one.
    """
    out: list[tuple[str, float]] = []
    for token_idx, lm_indices in enumerate(alignment.spacy_to_lm):
        token = doc[token_idx]
        if token.is_punct or token.is_space:
            continue

        total = 0.0
        scored = False
        for lm_idx in lm_indices:
            if lm_idx >= len(logprobs.logprobs):
                continue
            value = logprobs.logprobs[lm_idx]
            if value is None:
                continue
            total += -value
            scored = True

        if scored:
            out.append((token.text, total))
    return out


class MeanSurprisal(FeatureComputer):
    name = "mean_surprisal"
    tier = 3
    requires = (LM_TOKEN_LOGPROBS, SPACY_DOC, ALIGNMENT_LM_TO_SPACY)

    def compute(self, ctx: AnalysisContext) -> float | None:
        doc = ctx.get(SPACY_DOC)
        logprobs: TokenLogProbs = ctx.get(LM_TOKEN_LOGPROBS)
        alignment: LmToSpacyAlignment = ctx.get(ALIGNMENT_LM_TO_SPACY)

        values = [value for _, value in word_surprisals(doc, logprobs, alignment)]
        if not values:
            return None
        return round(sum(values) / len(values), 4)
