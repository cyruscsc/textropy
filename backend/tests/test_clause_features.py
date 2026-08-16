"""Tier 1 clause features (specs_features.md §3).

These assert against sentences whose parse was verified in `en_core_web_sm`, not sentences
that *ought* to parse a given way — the spec's §9.4 rule, and §10 records two ordinary
sentences the small model gets wrong. `test_parse_shape_underpinning_the_counts` pins the
parse itself, so a model upgrade that changes these numbers fails with a diagnosis rather
than a bare count mismatch.
"""

from __future__ import annotations

import pytest

from app.features.tier1.clause import (
    ADJECTIVE_CLAUSE_DEPS,
    ADVERBIAL_CLAUSE_DEPS,
    NOUN_CLAUSE_DEPS,
    is_infinitive_clause,
)

CLAUSE_KEYS = (
    "infinitive_clause_count",
    "noun_clause_count",
    "adjective_clause_count",
    "adverbial_clause_count",
)


def analyze(client, text: str) -> dict:
    response = client.post(
        "/api/v1/analyze",
        json={"mode": "single", "texts": [text], "tiers": [1]},
    )
    assert response.status_code == 200
    return response.json()["results"][0]["features"]["tier1"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # (infinitive, noun, adjective, adverbial)
        ("He wants to leave early.", (1, 0, 0, 0)),
        ("She said that he was tired.", (0, 1, 0, 0)),
        ("He insisted on leaving early.", (0, 1, 0, 0)),  # pcomp
        ("I know the man who left.", (0, 0, 1, 0)),  # relcl
        ("The book that she read was long.", (0, 0, 1, 0)),
        ("She smiled when he arrived.", (0, 0, 0, 1)),
        ("The cat sat on the mat.", (0, 0, 0, 0)),  # no subordination at all
    ],
)
def test_each_clause_type_is_counted(client, text, expected):
    tier1 = analyze(client, text)
    assert tuple(tier1[key] for key in CLAUSE_KEYS) == expected


def test_categories_overlap_by_design(client):
    """`To err is human.` is one clause counted twice — specs_features.md §3.2.

    The infinitive is also the clausal subject, so it is both infinitival and nominal. This
    is the documented reason no total may be derived by summing the four counts.
    """
    tier1 = analyze(client, "To err is human.")

    assert tier1["infinitive_clause_count"] == 1
    assert tier1["noun_clause_count"] == 1
    assert tier1["adjective_clause_count"] == 0
    assert tier1["adverbial_clause_count"] == 0


def test_counts_accumulate_across_sentences(client):
    """Counts are per text, not per sentence, and independent clause types add up."""
    tier1 = analyze(
        client,
        "He wants to leave early. She smiled when he arrived. I know the man who left.",
    )

    assert tier1["infinitive_clause_count"] == 1
    assert tier1["adverbial_clause_count"] == 1
    assert tier1["adjective_clause_count"] == 1


def test_text_without_words_counts_no_clauses(client):
    tier1 = analyze(client, "...")

    assert all(tier1[key] == 0 for key in CLAUSE_KEYS)


def test_semicolon_hazard_is_still_present(client):
    """Pins the known parser artifact from specs_features.md §3.3.

    `The cat sat; the dog barked.` is a compound sentence, but the parser makes the first
    clause a `ccomp`, so it counts as a noun clause. Decision 2 accepted this rather than
    special-casing it. This test exists so the behaviour is visible and intentional — if a
    model upgrade fixes the parse, this failing is the signal to update §3.3, not a bug.
    """
    tier1 = analyze(client, "The cat sat; the dog barked.")

    assert tier1["noun_clause_count"] == 1


def test_parse_shape_underpinning_the_counts(client):
    """The dependency labels the counts are built on, asserted directly.

    Counting logic and parser behaviour fail differently; separating them means a broken
    count says which of the two moved.
    """
    import spacy

    doc = spacy.load("en_core_web_sm")("He wants to leave early.")
    infinitives = [t for t in doc if is_infinitive_clause(t)]

    assert [t.text for t in infinitives] == ["leave"]
    assert infinitives[0].tag_ == "VB"
    # A `TO` aux must be present; "early"/advmod also hangs off `leave`, so the predicate
    # tests for membership rather than for it being the only child.
    assert ("aux", "TO") in [(c.dep_, c.tag_) for c in infinitives[0].children]
    # The label an infinitive surfaces under varies, which is why it is not the predicate.
    assert infinitives[0].dep_ == "xcomp"
    assert infinitives[0].dep_ not in NOUN_CLAUSE_DEPS


def test_dep_sets_are_disjoint_from_each_other():
    """The three label-based sets must not share a label, or one clause counts twice.

    Overlap between *categories* is expected (§3.2) and comes from a token matching two
    different predicates; overlap between the label sets themselves would be a typo.
    """
    assert NOUN_CLAUSE_DEPS.isdisjoint(ADJECTIVE_CLAUSE_DEPS)
    assert NOUN_CLAUSE_DEPS.isdisjoint(ADVERBIAL_CLAUSE_DEPS)
    assert ADJECTIVE_CLAUSE_DEPS.isdisjoint(ADVERBIAL_CLAUSE_DEPS)
    # Decision 1: infinitival complements are not noun clauses.
    assert "xcomp" not in NOUN_CLAUSE_DEPS
