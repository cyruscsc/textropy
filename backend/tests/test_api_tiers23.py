"""Tier 2/3 tests. Marked `heavy` — they load the transformer models.

Run with `uv run pytest -m heavy`; the default suite excludes nothing, so use
`-m "not heavy"` for a fast Tier 1-only pass.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.heavy

POSITIVE = "This film was wonderful. I loved every single minute of it."
TEXT_A = "The cat sat on the mat. It was a comfortable mat, and the cat loved it."
TEXT_B = "A feline rested upon the rug. The rug felt pleasant, so the animal stayed."


def _tier(client, mode, texts, tiers, key):
    body = client.post(
        "/api/v1/analyze", json={"mode": mode, "texts": texts, "tiers": tiers}
    ).json()
    return body, key


def test_tier2_single(client):
    response = client.post(
        "/api/v1/analyze", json={"mode": "single", "texts": [POSITIVE], "tiers": [2]}
    )
    assert response.status_code == 200
    tier2 = response.json()["results"][0]["features"]["tier2"]

    assert tier2["sentiment"]["label"] == "positive"
    assert 0.0 <= tier2["sentiment"]["score"] <= 1.0
    assert 0.0 <= tier2["cohesion"]["mean_adjacent_similarity"] <= 1.0

    coref = tier2["coreference"]
    # Degrades to an availability marker when the optional `coref` extra is absent.
    if isinstance(coref, dict) and coref.get("available") is False:
        pytest.skip("fastcoref extra not installed")
    assert coref["chain_count"] >= 0


def test_tier3_single(client):
    response = client.post(
        "/api/v1/analyze", json={"mode": "single", "texts": [TEXT_A], "tiers": [3]}
    )
    assert response.status_code == 200
    tier3 = response.json()["results"][0]["features"]["tier3"]

    assert tier3["perplexity"] > 1.0
    assert tier3["mean_surprisal"] > 0.0


def test_perplexity_and_surprisal_are_consistent(client):
    """Both are in nats, so a lower-perplexity text must also be less surprising."""
    predictable = "the the the the the the the the the the"
    surprising = "quixotic zephyr galvanised the borogoves abstemiously"

    def tier3(text):
        return client.post(
            "/api/v1/analyze", json={"mode": "single", "texts": [text], "tiers": [3]}
        ).json()["results"][0]["features"]["tier3"]

    low, high = tier3(predictable), tier3(surprising)
    assert low["perplexity"] < high["perplexity"]
    assert low["mean_surprisal"] < high["mean_surprisal"]


def test_tier2_comparison_bounds(client):
    body = client.post(
        "/api/v1/analyze", json={"mode": "compare", "texts": [TEXT_A, TEXT_B], "tiers": [2]}
    ).json()
    tier2 = body["comparison"]["tier2"]

    assert -1.0 <= tier2["semantic_similarity"] <= 1.0
    assert tier2["wmd"] >= 0.0
    assert 0.0 <= tier2["pos_divergence"] <= 1.0
    assert 0.0 <= tier2["dep_divergence"] <= 1.0


def test_identical_texts_have_zero_divergence(client):
    body = client.post(
        "/api/v1/analyze", json={"mode": "compare", "texts": [TEXT_A, TEXT_A], "tiers": [2]}
    ).json()
    tier2 = body["comparison"]["tier2"]

    assert tier2["pos_divergence"] == 0.0
    assert tier2["dep_divergence"] == 0.0
    assert tier2["wmd"] == 0.0
    assert tier2["semantic_similarity"] == pytest.approx(1.0, abs=1e-3)


def test_tier3_comparison_is_asymmetric(client):
    """Spec §3.2: Tier 3 comparisons return both directions, and they differ."""
    body = client.post(
        "/api/v1/analyze", json={"mode": "compare", "texts": [TEXT_A, TEXT_B], "tiers": [3]}
    ).json()
    tier3 = body["comparison"]["tier3"]

    for name in ("cross_perplexity", "conditional_surprisal"):
        assert set(tier3[name]) == {"a_given_b", "b_given_a"}
        assert tier3[name]["a_given_b"] is not None
        assert tier3[name]["b_given_a"] is not None

    assert tier3["cross_perplexity"]["a_given_b"] != tier3["cross_perplexity"]["b_given_a"]


def test_context_lowers_perplexity(client):
    """A text preceded by a near-duplicate should be easier to predict than one that isn't."""
    repeated = "The cat sat on the mat."

    def cross(a, b):
        return client.post(
            "/api/v1/analyze", json={"mode": "compare", "texts": [a, b], "tiers": [3]}
        ).json()["comparison"]["tier3"]["cross_perplexity"]

    same = cross(repeated, repeated)["b_given_a"]
    different = cross("Quarterly revenue exceeded analyst forecasts.", repeated)["b_given_a"]
    assert same < different


def test_single_text_features_still_returned_in_compare_mode(client):
    """Spec §6: compare mode returns each text's own features *and* the comparison."""
    body = client.post(
        "/api/v1/analyze", json={"mode": "compare", "texts": [TEXT_A, TEXT_B], "tiers": [1, 2]}
    ).json()

    assert len(body["results"]) == 2
    for result in body["results"]:
        assert "tier1" in result["features"]
        assert "tier2" in result["features"]
    assert set(body["comparison"]) == {"tier1", "tier2"}
