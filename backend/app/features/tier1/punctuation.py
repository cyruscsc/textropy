"""Tier 1 punctuation features (specs_features.md §5).

The one Tier 1 group whose denominator is `punctuation_count` rather than `word_count`, and
the one whose tokens the rest of Tier 1 deliberately excludes (§1.2).

Terminal and internal partition the punctuation exactly, so the two counts sum to
`punctuation_count` and the two ratios sum to 1.0 whenever any punctuation is present.
"""

from __future__ import annotations

from typing import Any

from app.features.base import FeatureComputer
from app.features.tier1.stats import ratio
from app.pipeline.context import AnalysisContext
from app.signals.base import SPACY_DOC

# The Penn tag spaCy gives sentence-final punctuation. Matching the tag rather than the token
# text avoids an open-ended character list — but see `is_terminal_punctuation` for the one
# place the tagger is not reliable.
TERMINAL_PUNCT_TAG = "."


def punctuation_tokens(doc: Any) -> list[Any]:
    """Every punctuation token — the denominator for both ratios here."""
    return [token for token in doc if token.is_punct]


def is_terminal_punctuation(token: Any) -> bool:
    """Sentence-final punctuation: `.`, `!`, `?`.

    ⚠️ Ellipsis is decided by the tagger, not by this rule, and the tagger is inconsistent
    about it: `...` is tagged `:` (internal) in most contexts but `.` (terminal) in some, on
    the same three characters. So an ellipsis usually counts as internal. Recorded as a
    caveat in §5.1 rather than papered over here — special-casing the text would contradict
    the reason the tag test was chosen, and would wrongly mark a mid-sentence "He paused...
    then left" as terminal.
    """
    return token.is_punct and token.tag_ == TERMINAL_PUNCT_TAG


class PunctuationCount(FeatureComputer):
    name = "punctuation_count"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> int:
        return len(punctuation_tokens(ctx.get(SPACY_DOC)))


class TerminalPunctuationCount(FeatureComputer):
    name = "terminal_punctuation_count"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> int:
        return sum(1 for token in ctx.get(SPACY_DOC) if is_terminal_punctuation(token))


class InternalPunctuationCount(FeatureComputer):
    """Punctuation that is not sentence-final — commas, semicolons, dashes, brackets, quotes.

    Defined as the complement of terminal rather than by its own tag list, so the two counts
    partition `punctuation_count` by construction and cannot drift apart as tags are added.
    """

    name = "internal_punctuation_count"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> int:
        tokens = punctuation_tokens(ctx.get(SPACY_DOC))
        return sum(1 for token in tokens if not is_terminal_punctuation(token))


class InternalPunctuationRatio(FeatureComputer):
    name = "internal_punctuation_ratio"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> float:
        tokens = punctuation_tokens(ctx.get(SPACY_DOC))
        internal = sum(1 for token in tokens if not is_terminal_punctuation(token))
        return ratio(internal, len(tokens))


class TerminalPunctuationRatio(FeatureComputer):
    """`terminal_punctuation_count / punctuation_count`.

    Computed from its own count rather than as `1 - internal_punctuation_ratio`, so neither
    ratio inherits the other's rounding error — the same rule the lexical densities follow.
    """

    name = "terminal_punctuation_ratio"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> float:
        tokens = punctuation_tokens(ctx.get(SPACY_DOC))
        terminal = sum(1 for token in tokens if is_terminal_punctuation(token))
        return ratio(terminal, len(tokens))
