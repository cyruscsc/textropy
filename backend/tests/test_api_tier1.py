"""End-to-end API tests for Tier 1 (spaCy only — no Tier 2/3 model downloads)."""

from __future__ import annotations

TEXT_A = "The cat sat on the mat. It was a comfortable mat."
TEXT_B = "A feline rested upon the rug. The rug was pleasant."


def test_health_reports_model_status(client):
    body = client.get("/api/v1/health").json()

    assert body["status"] == "ok"
    assert body["ready"] is True  # tier 1 is preloaded by default
    assert body["models"]["spacy"] == "loaded"


def test_catalog_covers_every_spec_feature(client):
    features = client.get("/api/v1/features").json()["features"]
    by_name = {f["name"]: f for f in features}

    # Spec §3.1 single-text
    assert {
        "word_count",
        "unique_word_count",
        "content_word_count",
        "function_word_count",
        "ttr",
        "sentiment",
        "coreference",
        "cohesion",
        "perplexity",
        "mean_surprisal",
    } <= set(by_name)
    # Spec §3.2 comparison
    assert {
        "levenshtein",
        "lcs_length",
        "ngram_overlap",
        "tfidf_cosine",
        "semantic_similarity",
        "wmd",
        "pos_divergence",
        "dep_divergence",
        "cross_perplexity",
        "conditional_surprisal",
    } <= set(by_name)

    assert by_name["word_count"]["scope"] == "single"
    assert by_name["levenshtein"]["scope"] == "comparison"
    assert by_name["cross_perplexity"]["symmetric"] is False
    assert by_name["levenshtein"]["symmetric"] is True


def test_single_mode_tier1(client):
    response = client.post(
        "/api/v1/analyze",
        json={"mode": "single", "texts": [TEXT_A], "tiers": [1]},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["mode"] == "single"
    assert body["comparison"] is None
    assert body["meta"]["tiers_computed"] == [1]
    assert set(body["meta"]["elapsed_ms"]) == {"signals", "features"}

    tier1 = body["results"][0]["features"]["tier1"]
    assert tier1["word_count"] == 11  # punctuation excluded
    assert tier1["content_word_count"] + tier1["function_word_count"] == tier1["word_count"]
    assert 0 < tier1["ttr"] <= 1
    # Only the requested tier is present.
    assert set(body["results"][0]["features"]) == {"tier1"}


def test_compare_mode_tier1(client):
    response = client.post(
        "/api/v1/analyze",
        json={"mode": "compare", "texts": [TEXT_A, TEXT_B], "tiers": [1]},
    )
    assert response.status_code == 200
    body = response.json()

    assert [r["text_index"] for r in body["results"]] == [0, 1]

    comparison = body["comparison"]["tier1"]
    assert set(comparison) == {"levenshtein", "lcs_length", "ngram_overlap", "tfidf_cosine"}
    assert comparison["levenshtein"] > 0
    assert 0.0 <= comparison["tfidf_cosine"] <= 1.0
    assert "comparison" in body["meta"]["elapsed_ms"]


def test_identical_texts_are_maximally_similar(client):
    body = client.post(
        "/api/v1/analyze",
        json={"mode": "compare", "texts": [TEXT_A, TEXT_A], "tiers": [1]},
    ).json()

    comparison = body["comparison"]["tier1"]
    assert comparison["levenshtein"] == 0
    assert comparison["ngram_overlap"] == 1.0
    assert comparison["tfidf_cosine"] == 1.0


def test_symmetric_features_are_order_independent(client):
    def compare(first, second):
        return client.post(
            "/api/v1/analyze",
            json={"mode": "compare", "texts": [first, second], "tiers": [1]},
        ).json()["comparison"]["tier1"]

    assert compare(TEXT_A, TEXT_B) == compare(TEXT_B, TEXT_A)


def test_feature_names_override_ignores_tiers(client):
    body = client.post(
        "/api/v1/analyze",
        json={
            "mode": "single",
            "texts": [TEXT_A],
            "tiers": [1, 2, 3],
            "feature_names": ["word_count", "ttr"],
        },
    ).json()

    assert body["results"][0]["features"] == {
        "tier1": {"word_count": 11, "ttr": body["results"][0]["features"]["tier1"]["ttr"]}
    }
    assert body["meta"]["tiers_computed"] == [1]


def test_mode_and_text_count_must_agree(client):
    response = client.post(
        "/api/v1/analyze",
        json={"mode": "compare", "texts": [TEXT_A], "tiers": [1]},
    )
    assert response.status_code == 422


def test_blank_text_is_rejected(client):
    response = client.post(
        "/api/v1/analyze",
        json={"mode": "single", "texts": ["   "], "tiers": [1]},
    )
    assert response.status_code == 422


def test_unknown_feature_name_is_rejected(client):
    response = client.post(
        "/api/v1/analyze",
        json={"mode": "single", "texts": [TEXT_A], "feature_names": ["not_a_feature"]},
    )
    assert response.status_code == 422
    assert "not_a_feature" in response.json()["detail"]


def test_out_of_range_tier_is_rejected(client):
    response = client.post(
        "/api/v1/analyze",
        json={"mode": "single", "texts": [TEXT_A], "tiers": [4]},
    )
    assert response.status_code == 422
