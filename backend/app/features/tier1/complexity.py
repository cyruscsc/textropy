"""Tier 1 syntactic complexity features (specs_features.md §6).

Three mean/stdev pairs, each over a different series:

* MDD and tree depth are **per sentence**, over `content_sentences()`.
* Phrasal elaboration is **per noun**, over the whole document — so its `n` is the number of
  nouns, not the number of sentences, and a text without nouns yields `0.0` for both.

Per-unit values are returned **unrounded**; only `stats.mean`/`stats.stdev` round, at the point
of return. Rounding a per-sentence MDD before averaging would be rounding an intermediate,
which §1.6 forbids.
"""

from __future__ import annotations

from typing import Any

from app.features.base import FeatureComputer
from app.features.tier1.stats import mean, stdev
from app.pipeline.context import AnalysisContext
from app.signals.base import SPACY_DOC
from app.signals.spacy_extractor import content_sentences

# Phrasal elaboration counts dependents of nominals only — a narrower set than `CONTENT_POS`,
# which also admits VERB/ADJ/ADV.
NOUN_POS = frozenset({"NOUN", "PROPN"})

ROOT_DEP = "ROOT"


def mean_dependency_distance(sent: Any) -> float:
    """Mean |head − dependent| over the sentence's arcs, in token positions.

    Distances are measured on `token.i`, an index into the whole doc, so they count
    punctuation positions whether or not the arc itself is a `punct` arc.

    Every non-ROOT token contributes an arc, `punct` included (Decision 3). A sentence with no
    arcs — a lone root — has no distances to average and gives `0.0`.
    """
    distances = [abs(token.i - token.head.i) for token in sent if token.dep_ != ROOT_DEP]
    if not distances:
        return 0.0
    return sum(distances) / len(distances)


def tree_depth(sent: Any) -> int:
    """Depth of the sentence's dependency tree in edges, ROOT at 0.

    Memoised: each token walks up only until it meets a token whose depth is already known,
    so the whole sentence costs O(n) rather than the O(n·depth) a naive per-token walk would.
    The `head is self` guard is defensive — a token that is not ROOT but heads itself would
    otherwise spin forever on a degenerate parse.
    """
    depths: dict[int, int] = {}

    for token in sent:
        chain: list[Any] = []
        current = token
        while current.i not in depths and current.dep_ != ROOT_DEP and current.head.i != current.i:
            chain.append(current)
            current = current.head

        depth = depths.setdefault(current.i, 0)
        for ancestor in reversed(chain):
            depth += 1
            depths[ancestor.i] = depth

    return max(depths.values(), default=0)


def phrasal_elaboration(noun: Any) -> int:
    """Direct dependents of a nominal, punctuation excluded.

    Direct children only (Decision 4): in "The very tall man with a hat", `man` scores 3 —
    `The`/det, `tall`/amod, `with`/prep. `very` modifies `tall`, so it is a grandchild and
    does not count. Subtree size is a different measurement and would need its own name.
    """
    return sum(1 for child in noun.children if not child.is_punct)


def mdd_series(doc: Any) -> list[float]:
    return [mean_dependency_distance(sent) for sent in content_sentences(doc)]


def depth_series(doc: Any) -> list[int]:
    return [tree_depth(sent) for sent in content_sentences(doc)]


def elaboration_series(doc: Any) -> list[int]:
    """Per-noun dependent counts across the document — not per sentence."""
    return [phrasal_elaboration(token) for token in doc if token.pos_ in NOUN_POS]


class MddMean(FeatureComputer):
    name = "mdd_mean"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> float:
        return mean(mdd_series(ctx.get(SPACY_DOC)))


class MddStdev(FeatureComputer):
    name = "mdd_stdev"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> float:
        return stdev(mdd_series(ctx.get(SPACY_DOC)))


class DependencyDepthMean(FeatureComputer):
    name = "dependency_depth_mean"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> float:
        return mean(depth_series(ctx.get(SPACY_DOC)))


class DependencyDepthStdev(FeatureComputer):
    name = "dependency_depth_stdev"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> float:
        return stdev(depth_series(ctx.get(SPACY_DOC)))


class PhrasalElaborationMean(FeatureComputer):
    name = "phrasal_elaboration_mean"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> float:
        return mean(elaboration_series(ctx.get(SPACY_DOC)))


class PhrasalElaborationStdev(FeatureComputer):
    name = "phrasal_elaboration_stdev"
    tier = 1
    requires = (SPACY_DOC,)

    def compute(self, ctx: AnalysisContext) -> float:
        return stdev(elaboration_series(ctx.get(SPACY_DOC)))
