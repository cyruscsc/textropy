"""Tier 1 clause features (specs_features.md §3).

Each computer counts clause *instances across the whole text*, not per sentence: the value is
the number of tokens in the parse matching a dependency predicate.

The four counts deliberately **overlap and do not partition** the clauses of a text. `To err
is human.` holds one clause that is both infinitival (`TO`+`VB`) and nominal (`csubj`), and it
increments two of them. Do not derive a total by summing these, and do not build densities
over that sum (§3.2).
"""

from __future__ import annotations

from typing import Any

from app.features.base import FeatureComputer
from app.pipeline.context import AnalysisContext
from app.signals.base import SPACY_DOC

# Dependency labels per specs_features.md §3, named rather than inlined so the spec's
# definitions stay greppable and a typo reads as a wrong-looking constant instead of a
# silently-zero count.
#
# `xcomp` is deliberately absent from the noun-clause set (§11, Decision 1): infinitival
# complements are counted by `infinitive_clause_count`, and adding `xcomp` here would make
# most of them increment both.
NOUN_CLAUSE_DEPS = frozenset({"ccomp", "csubj", "csubjpass", "pcomp"})
ADJECTIVE_CLAUSE_DEPS = frozenset({"relcl", "acl"})
ADVERBIAL_CLAUSE_DEPS = frozenset({"advcl"})


def is_infinitive_clause(token: Any) -> bool:
    """Whether `token` heads an infinitive clause.

    Keyed on the `TO`+`VB` shape rather than the token's own dependency label, because an
    infinitive clause surfaces under several: `xcomp` in "He wants to leave early", `csubj`
    in "To err is human". The shape is invariant across both, the label is not.
    """
    if token.tag_ != "VB":
        return False
    return any(child.dep_ == "aux" and child.tag_ == "TO" for child in token.children)


def count_clause_deps(doc: Any, deps: frozenset[str]) -> int:
    """Tokens whose dependency label falls in `deps`."""
    return sum(1 for token in doc if token.dep_ in deps)


class InfinitiveClauseCount(FeatureComputer):
    name = "infinitive_clause_count"
    tier = 1
    requires = (SPACY_DOC,)
    approximate = True

    def compute(self, ctx: AnalysisContext) -> int:
        return sum(1 for token in ctx.get(SPACY_DOC) if is_infinitive_clause(token))


class NounClauseCount(FeatureComputer):
    """Clauses filling a nominal slot — `ccomp`, `csubj`, `csubjpass`, `pcomp`."""

    name = "noun_clause_count"
    tier = 1
    requires = (SPACY_DOC,)
    approximate = True

    def compute(self, ctx: AnalysisContext) -> int:
        return count_clause_deps(ctx.get(SPACY_DOC), NOUN_CLAUSE_DEPS)


class AdjectiveClauseCount(FeatureComputer):
    """Clauses modifying a nominal — finite relatives (`relcl`) and participials (`acl`)."""

    name = "adjective_clause_count"
    tier = 1
    requires = (SPACY_DOC,)
    approximate = True

    def compute(self, ctx: AnalysisContext) -> int:
        return count_clause_deps(ctx.get(SPACY_DOC), ADJECTIVE_CLAUSE_DEPS)


class AdverbialClauseCount(FeatureComputer):
    name = "adverbial_clause_count"
    tier = 1
    requires = (SPACY_DOC,)
    approximate = True

    def compute(self, ctx: AnalysisContext) -> int:
        return count_clause_deps(ctx.get(SPACY_DOC), ADVERBIAL_CLAUSE_DEPS)
