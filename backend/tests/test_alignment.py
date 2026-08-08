"""Tests for the LM-to-spaCy alignment (spec §4: deterministic, no model)."""

from __future__ import annotations

from app.signals.alignment import align_offsets


def test_one_to_one_alignment():
    # "ab cd" -> spaCy ["ab", "cd"], LM ["ab", " cd"]
    alignment = align_offsets([(0, 2), (3, 5)], [(0, 2), (2, 5)])

    assert alignment.spacy_to_lm == [[0], [1]]
    assert alignment.lm_to_spacy == [0, 1]


def test_word_split_across_multiple_subwords():
    """One spaCy token covered by three BPE pieces must collect all three."""
    alignment = align_offsets([(0, 9)], [(0, 3), (3, 6), (6, 9)])

    assert alignment.spacy_to_lm == [[0, 1, 2]]
    assert alignment.lm_to_spacy == [0, 0, 0]


def test_subword_spanning_two_words_attributes_to_both():
    # A single LM token covering "ab cd" overlaps both spaCy tokens.
    alignment = align_offsets([(0, 2), (3, 5)], [(0, 5)])

    assert alignment.spacy_to_lm == [[0], [0]]
    # lm_to_spacy records the first token it overlaps.
    assert alignment.lm_to_spacy == [0]


def test_empty_spans_are_ignored():
    alignment = align_offsets([(0, 2)], [(0, 0), (0, 2)])

    assert alignment.spacy_to_lm == [[1]]
    assert alignment.lm_to_spacy == [None, 0]


def test_empty_inputs():
    assert align_offsets([], []).spacy_to_lm == []
    assert align_offsets([], [(0, 3)]).lm_to_spacy == [None]
    assert align_offsets([(0, 3)], []).spacy_to_lm == [[]]


def test_leading_whitespace_offsets():
    """GPT-2 offsets usually include the leading space; the word must still match."""
    # "the cat": spaCy [(0,3),(4,7)], GPT-2 [(0,3),(3,7)] where token 1 is " cat".
    alignment = align_offsets([(0, 3), (4, 7)], [(0, 3), (3, 7)])

    assert alignment.spacy_to_lm == [[0], [1]]
