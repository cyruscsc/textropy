"""Tier 1 punctuation features (specs_features.md §5).

Fixture counts were read off the real tagger before being asserted (§9.4). The partition
invariant — terminal + internal covering `punctuation_count` — is asserted directly, since it
is what breaks silently if the terminal test and its complement ever drift apart.
"""

from __future__ import annotations

import pytest

# ',' '!' '?' '...' '(' '--' '.' ')' — eight punctuation tokens, three of them terminal
# ('!', '?', '.'). The ellipsis is tagged ':' here, i.e. internal — see §5.1.
MIXED = "Hello, world! Is this real? Yes... (Maybe -- perhaps.)"


def analyze(client, text: str) -> dict:
    response = client.post(
        "/api/v1/analyze",
        json={"mode": "single", "texts": [text], "tiers": [1]},
    )
    assert response.status_code == 200
    return response.json()["results"][0]["features"]["tier1"]


def test_counts_and_ratios(client):
    tier1 = analyze(client, MIXED)

    assert tier1["punctuation_count"] == 8
    assert tier1["terminal_punctuation_count"] == 3
    assert tier1["internal_punctuation_count"] == 5
    assert tier1["terminal_punctuation_ratio"] == 0.375
    assert tier1["internal_punctuation_ratio"] == 0.625


def test_terminal_and_internal_partition_the_punctuation(client):
    tier1 = analyze(client, MIXED)

    assert (
        tier1["internal_punctuation_count"] + tier1["terminal_punctuation_count"]
        == tier1["punctuation_count"]
    )
    assert tier1["internal_punctuation_ratio"] + tier1["terminal_punctuation_ratio"] == (
        pytest.approx(1.0, abs=1e-4)
    )


@pytest.mark.parametrize(
    ("text", "terminal"),
    [
        ("The cat sat.", 1),
        ("Stop!", 1),
        ("Really?", 1),
        ("One. Two! Three?", 3),
    ],
)
def test_sentence_final_marks_are_terminal(client, text, terminal):
    tier1 = analyze(client, text)

    assert tier1["terminal_punctuation_count"] == terminal
    assert tier1["internal_punctuation_count"] == 0


@pytest.mark.parametrize(
    "text",
    [
        "Wait, stop",  # comma
        "The cat sat; the dog barked",  # semicolon
        "He left -- quickly",  # dash
        "She said (quietly)",  # brackets
    ],
)
def test_non_final_marks_are_internal(client, text):
    tier1 = analyze(client, text)

    assert tier1["terminal_punctuation_count"] == 0
    assert tier1["internal_punctuation_count"] == tier1["punctuation_count"] > 0
    assert tier1["internal_punctuation_ratio"] == 1.0


def test_text_without_punctuation_gives_zero_ratios(client):
    """The §1.4 zero-denominator case that only this group can reach."""
    tier1 = analyze(client, "No punctuation here at all")

    assert tier1["punctuation_count"] == 0
    assert tier1["internal_punctuation_count"] == 0
    assert tier1["terminal_punctuation_count"] == 0
    assert tier1["internal_punctuation_ratio"] == 0.0
    assert tier1["terminal_punctuation_ratio"] == 0.0


def test_punctuation_only_text_is_still_counted(client):
    """`"..."` has no words but does have punctuation — the mirror of the lexical edge case.

    Also pins the ellipsis behaviour recorded in §5.1: the tagger calls this `:`, so it
    counts as internal despite ending the text.
    """
    tier1 = analyze(client, "...")

    assert tier1["word_count"] == 0
    assert tier1["punctuation_count"] == 1
    assert tier1["internal_punctuation_count"] == 1
    assert tier1["terminal_punctuation_count"] == 0


def test_punctuation_is_excluded_from_the_word_count(client):
    """The two groups read the same doc and must not overlap (§1.2)."""
    tier1 = analyze(client, MIXED)

    assert tier1["word_count"] == 8  # Hello world Is this real Yes Maybe perhaps
    assert tier1["punctuation_count"] == 8
