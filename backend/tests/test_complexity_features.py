"""Tier 1 complexity features (specs_features.md §6).

Every expected value here was derived from the real parse and checked by hand against the
arc list — see `test_mdd_matches_the_hand_computed_arcs`, which spells out the arithmetic
rather than trusting the aggregate.
"""

from __future__ import annotations

import pytest
import spacy

from app.features.tier1.complexity import (
    depth_series,
    elaboration_series,
    mdd_series,
    mean_dependency_distance,
    phrasal_elaboration,
    tree_depth,
)

COMPLEXITY_KEYS = (
    "mdd_mean",
    "mdd_stdev",
    "dependency_depth_mean",
    "dependency_depth_stdev",
    "phrasal_elaboration_mean",
    "phrasal_elaboration_stdev",
)


@pytest.fixture(scope="module")
def nlp():
    return spacy.load("en_core_web_sm")


def analyze(client, text: str) -> dict:
    response = client.post(
        "/api/v1/analyze",
        json={"mode": "single", "texts": [text], "tiers": [1]},
    )
    assert response.status_code == 200
    return response.json()["results"][0]["features"]["tier1"]


def test_mdd_matches_the_hand_computed_arcs(nlp):
    """The arithmetic, spelled out, for "The cat sat on the mat."

    Arcs (dependent → head, by token index):
        The(0)→cat(1) 1 · cat(1)→sat(2) 1 · on(3)→sat(2) 1
        the(4)→mat(5) 1 · mat(5)→on(3)  2 · .(6)→sat(2)  4
    Six arcs, total 10, so MDD = 10/6. `sat` is ROOT and contributes none.

    The `.` arc contributes 4 — the largest single distance in a six-word sentence. That is
    Decision 3's accepted cost, made visible here rather than buried in an aggregate.
    """
    sent = next(iter(nlp("The cat sat on the mat.").sents))

    distances = [abs(t.i - t.head.i) for t in sent if t.dep_ != "ROOT"]
    assert sorted(distances) == [1, 1, 1, 1, 2, 4]
    assert mean_dependency_distance(sent) == pytest.approx(10 / 6)


def test_punctuation_arc_is_included(nlp):
    """Decision 3, asserted as a difference rather than a claim."""
    sent = next(iter(nlp("The cat sat on the mat.").sents))

    with_punct = mean_dependency_distance(sent)
    without = [abs(t.i - t.head.i) for t in sent if t.dep_ != "ROOT" and not t.is_punct]
    assert with_punct != pytest.approx(sum(without) / len(without))


def test_tree_depth_counts_edges_from_root(nlp):
    """`the → mat → on → sat` is the deepest chain, so depth is 3 edges."""
    sent = next(iter(nlp("The cat sat on the mat.").sents))
    assert tree_depth(sent) == 3

    # A one-token sentence is all root, so depth 0 — not 1.
    assert tree_depth(next(iter(nlp("Go").sents))) == 0


def test_phrasal_elaboration_counts_direct_children_only(nlp):
    """The spec's worked example (§6.3): `man` scores 3, and `very` is not one of them."""
    doc = nlp("The very tall man with a hat waved.")
    man = next(t for t in doc if t.text == "man")

    assert [(c.text, c.dep_) for c in man.children] == [
        ("The", "det"),
        ("tall", "amod"),
        ("with", "prep"),
    ]
    assert phrasal_elaboration(man) == 3
    # "very" modifies "tall", so it is a grandchild of "man".
    assert next(t for t in doc if t.text == "very").head.text == "tall"
    # Subtree size is the rejected alternative and is a different number entirely.
    assert len(list(man.subtree)) == 7


def test_single_sentence_values(client):
    tier1 = analyze(client, "The cat sat on the mat.")

    assert tier1["mdd_mean"] == 1.6667
    assert tier1["dependency_depth_mean"] == 3.0
    # cat and mat each take one determiner.
    assert tier1["phrasal_elaboration_mean"] == 1.0
    # One sentence, so every per-sentence stdev is 0.0 (§1.5).
    assert tier1["mdd_stdev"] == 0.0
    assert tier1["dependency_depth_stdev"] == 0.0


def test_stdev_is_nonzero_across_uneven_sentences(client):
    """Two sentences of different shapes must move the per-sentence stdevs off zero."""
    tier1 = analyze(client, "The cat sat on the mat. Dogs bark.")

    assert tier1["mdd_mean"] == 1.3333
    assert tier1["mdd_stdev"] == 0.3333
    assert tier1["dependency_depth_mean"] == 2.0
    assert tier1["dependency_depth_stdev"] == 1.0


def test_elaboration_series_is_per_noun_not_per_sentence(client, nlp):
    """Its `n` is the noun count, which is what makes it differ from the other two pairs."""
    text = "The very tall man with a hat waved."
    doc = nlp(text)

    assert elaboration_series(doc) == [3, 1]  # man, hat
    assert len(mdd_series(doc)) == len(depth_series(doc)) == 1  # one sentence

    tier1 = analyze(client, text)
    assert tier1["phrasal_elaboration_mean"] == 2.0
    assert tier1["phrasal_elaboration_stdev"] == 1.0


def test_text_without_nouns_gives_zero_elaboration(client):
    tier1 = analyze(client, "They ran quickly.")

    assert tier1["phrasal_elaboration_mean"] == 0.0
    assert tier1["phrasal_elaboration_stdev"] == 0.0
    # The per-sentence pairs are unaffected — the series are independent.
    assert tier1["mdd_mean"] > 0.0


def test_punctuation_only_text_is_all_zero(client):
    """No content sentences and no nouns, so all three series are empty (§1.5)."""
    tier1 = analyze(client, "...")

    assert all(tier1[key] == 0.0 for key in COMPLEXITY_KEYS)


def test_lone_token_sentence_has_no_arcs(client):
    """A sentence that is only a root has nothing to average — 0.0, not a crash."""
    tier1 = analyze(client, "Go")

    assert tier1["mdd_mean"] == 0.0
    assert tier1["dependency_depth_mean"] == 0.0


def test_depth_memoisation_matches_a_naive_walk(nlp):
    """The memoised walk must agree with the obvious O(n·depth) definition."""

    def naive_depth(token) -> int:
        depth = 0
        while token.dep_ != "ROOT" and token.head.i != token.i:
            token = token.head
            depth += 1
        return depth

    text = (
        "Because it rained the game that everyone wanted was cancelled, "
        "and we went home to the house on the hill."
    )
    for sent in nlp(text).sents:
        assert tree_depth(sent) == max(naive_depth(t) for t in sent)
