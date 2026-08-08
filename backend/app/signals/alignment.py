"""`alignment.lm_to_spacy` — deterministic subword-to-word mapping (spec §4, no model).

DistilGPT2 scores BPE subwords; users care about words. This maps the two tokenizations
onto each other through character offsets, letting Tier 3 report surprisal per spaCy
token (summing the subwords that compose it) instead of per subword.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from typing import Any

from app.pipeline.context import AnalysisContext
from app.signals.base import (
    ALIGNMENT_LM_TO_SPACY,
    LM_TOKEN_LOGPROBS,
    SPACY_DOC,
    SignalExtractor,
)
from app.signals.lm_extractor import TokenLogProbs


@dataclass(frozen=True)
class LmToSpacyAlignment:
    """Bidirectional index map between LM subwords and spaCy tokens."""

    spacy_to_lm: list[list[int]]  # spaCy token index -> LM token indices covering it
    lm_to_spacy: list[int | None]  # LM token index -> spaCy token index (first overlap)


def align_offsets(
    spacy_spans: list[tuple[int, int]],
    lm_offsets: list[tuple[int, int]],
) -> LmToSpacyAlignment:
    """Map character spans to character spans.

    An LM token is attributed to the first spaCy token whose span it overlaps. Pure
    interval arithmetic — no model, fully deterministic, so it is unit-testable without
    loading DistilGPT2.
    """
    spacy_to_lm: list[list[int]] = [[] for _ in spacy_spans]
    lm_to_spacy: list[int | None] = [None] * len(lm_offsets)

    if not spacy_spans:
        return LmToSpacyAlignment(spacy_to_lm=spacy_to_lm, lm_to_spacy=lm_to_spacy)

    starts = [s for s, _ in spacy_spans]

    for lm_idx, (lm_start, lm_end) in enumerate(lm_offsets):
        if lm_end <= lm_start:  # empty span (e.g. a pure-whitespace BPE token)
            continue

        # Candidate spaCy token: the last one starting at or before lm_start.
        pos = bisect_left(starts, lm_start + 1) - 1
        if pos < 0:
            pos = 0

        # Walk forward while spans still start before the LM token ends.
        for cand in range(pos, len(spacy_spans)):
            s_start, s_end = spacy_spans[cand]
            if s_start >= lm_end:
                break
            if s_start < lm_end and lm_start < s_end:  # overlap
                spacy_to_lm[cand].append(lm_idx)
                if lm_to_spacy[lm_idx] is None:
                    lm_to_spacy[lm_idx] = cand

    return LmToSpacyAlignment(spacy_to_lm=spacy_to_lm, lm_to_spacy=lm_to_spacy)


def spacy_spans(doc: Any) -> list[tuple[int, int]]:
    return [(t.idx, t.idx + len(t.text)) for t in doc]


class LmToSpacyAlignmentExtractor(SignalExtractor):
    name = ALIGNMENT_LM_TO_SPACY
    depends_on = (SPACY_DOC, LM_TOKEN_LOGPROBS)

    def extract(self, ctx: AnalysisContext) -> LmToSpacyAlignment:
        doc = ctx.get(SPACY_DOC)
        logprobs: TokenLogProbs = ctx.get(LM_TOKEN_LOGPROBS)
        return align_offsets(spacy_spans(doc), logprobs.offsets)
