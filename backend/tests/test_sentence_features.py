"""Tier 1 sentence features (specs_features.md §4).

Classification fixtures were verified against `en_core_web_sm` before being asserted (§9.4).
The partition invariant in §4.2 — four counts covering `sentence_count`, four densities summing
to 1 — is asserted directly, since it is the property that would break silently if a class were
added or the classifier drifted.
"""

from __future__ import annotations

import pytest

from app.features.tier1.stats import mean, ratio, stdev

CLASS_COUNT_KEYS = (
    "simple_sentence_count",
    "compound_sentence_count",
    "complex_sentence_count",
    "compound_complex_sentence_count",
)
CLASS_DENSITY_KEYS = (
    "simple_sentence_density",
    "compound_sentence_density",
    "complex_sentence_density",
    "compound_complex_sentence_density",
)

# One sentence of each class, verified in the parser.
MIXED = (
    "The cat sat on the mat. "
    "The cat sat and the dog barked. "
    "Because it rained, the game was cancelled. "
    "Because it rained, the game was cancelled and we went home."
)


def analyze(client, text: str) -> dict:
    response = client.post(
        "/api/v1/analyze",
        json={"mode": "single", "texts": [text], "tiers": [1]},
    )
    assert response.status_code == 200
    return response.json()["results"][0]["features"]["tier1"]


@pytest.mark.parametrize(
    ("text", "expected_class"),
    [
        ("The cat sat on the mat.", "simple"),
        # Compound predicate, not a compound sentence: "went" has no subject of its own.
        ("He came and went.", "simple"),
        # Non-finite complements are phrases, not subordinate clauses (§4.3).
        ("He wants to leave early.", "simple"),
        ("The tired man slept.", "simple"),
        ("The cat sat and the dog barked.", "compound"),
        # Existential "there" counts as a subject, so this coordinates two clauses.
        ("There is a problem and there are others.", "compound"),
        ("Because it rained, the game was cancelled.", "complex"),
        ("I know the man who left.", "complex"),
        ("Because it rained, the game was cancelled and we went home.", "compound_complex"),
    ],
)
def test_sentence_classification(client, text, expected_class):
    tier1 = analyze(client, text)
    key = f"{expected_class}_sentence_count"

    assert tier1["sentence_count"] == 1
    assert tier1[key] == 1, f"expected {text!r} to classify as {expected_class}"
    # Exactly one class claims it.
    assert sum(tier1[k] for k in CLASS_COUNT_KEYS) == 1


def test_classes_partition_the_sentences(client):
    tier1 = analyze(client, MIXED)

    assert tier1["sentence_count"] == 4
    assert tuple(tier1[k] for k in CLASS_COUNT_KEYS) == (1, 1, 1, 1)
    # §4.2: the four counts cover every sentence, with none double-counted.
    assert sum(tier1[k] for k in CLASS_COUNT_KEYS) == tier1["sentence_count"]
    assert sum(tier1[k] for k in CLASS_DENSITY_KEYS) == pytest.approx(1.0, abs=1e-4)
    assert all(tier1[k] == 0.25 for k in CLASS_DENSITY_KEYS)


def test_sentence_length_series(client):
    # "The cat sat on the mat" = 6 word tokens; "It was a comfortable mat" = 5.
    tier1 = analyze(client, "The cat sat on the mat. It was a comfortable mat.")

    assert tier1["sentence_count"] == 2
    assert tier1["sentence_length_mean"] == 5.5
    assert tier1["sentence_length_stdev"] == 0.5  # population form, not sample
    # The series is the same word definition the lexical group counts with.
    assert tier1["sentence_length_mean"] * tier1["sentence_count"] == tier1["word_count"]


def test_single_sentence_has_zero_stdev(client):
    tier1 = analyze(client, "The cat sat on the mat.")

    assert tier1["sentence_count"] == 1
    assert tier1["sentence_length_mean"] == 6.0
    assert tier1["sentence_length_stdev"] == 0.0  # sample stdev would be undefined here


def test_punctuation_only_text_has_no_sentences(client):
    """`"..."` parses as a sentence span with no word tokens — it must not be counted."""
    tier1 = analyze(client, "...")

    assert tier1["sentence_count"] == 0
    assert all(tier1[k] == 0 for k in CLASS_COUNT_KEYS)
    assert all(tier1[k] == 0.0 for k in CLASS_DENSITY_KEYS)
    assert tier1["sentence_length_mean"] == 0.0
    assert tier1["sentence_length_stdev"] == 0.0


def test_semicolon_hazard_classifies_as_complex(client):
    """Pins the §4.3 parser artifact.

    `The cat sat; the dog barked.` is a compound sentence, but the parser makes the first
    clause a `ccomp`, so it classifies as complex. Decision 2 accepted this rather than
    special-casing it; a model upgrade that fixes the parse should fail here and prompt a
    spec update, not a silent change in published numbers.
    """
    tier1 = analyze(client, "The cat sat; the dog barked.")

    assert tier1["complex_sentence_count"] == 1
    assert tier1["compound_sentence_count"] == 0


# --- stats helpers (specs_features.md §1.4-1.6) ------------------------------------------


def test_ratio_returns_zero_on_zero_denominator():
    assert ratio(0, 0) == 0.0
    assert ratio(3, 4) == 0.75


def test_mean_and_stdev_on_empty_and_single_series():
    assert mean([]) == 0.0
    assert stdev([]) == 0.0
    assert mean([7]) == 7.0
    assert stdev([7]) == 0.0


def test_stdev_is_the_population_form():
    """Checked against numpy: ddof=0 gives 1.118 here, ddof=1 gives 1.291."""
    values = [1, 2, 3, 4]
    assert mean(values) == 2.5
    assert stdev(values) == pytest.approx(1.118, abs=1e-4)
    assert stdev(values) != pytest.approx(1.291, abs=1e-4)
