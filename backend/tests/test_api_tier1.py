"""End-to-end API tests for Tier 1 (spaCy only — no Tier 2/3 model downloads)."""

from __future__ import annotations

import pytest

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

    # Spec §3.1 single-text, plus the lemma pair added after the MVP spec was written
    assert {
        "word_count",
        "unique_word_count",
        "lemma_count",
        "unique_lemma_count",
        "content_word_count",
        "function_word_count",
        "content_word_density",
        "function_word_density",
        "ttr",
        # specs_features.md §3 — clause group
        "infinitive_clause_count",
        "noun_clause_count",
        "adjective_clause_count",
        "adverbial_clause_count",
        # §4 — sentence group
        "sentence_count",
        "simple_sentence_count",
        "compound_sentence_count",
        "complex_sentence_count",
        "compound_complex_sentence_count",
        "sentence_length_mean",
        "sentence_length_stdev",
        # §5 — punctuation group
        "punctuation_count",
        "internal_punctuation_count",
        "internal_punctuation_ratio",
        "terminal_punctuation_count",
        "terminal_punctuation_ratio",
        # §6 — complexity group
        "mdd_mean",
        "mdd_stdev",
        "dependency_depth_mean",
        "dependency_depth_stdev",
        "phrasal_elaboration_mean",
        "phrasal_elaboration_stdev",
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


def test_lemma_counts_collapse_inflection(client):
    # dogs/dog and barked/barks are two surface types each, but one lemma each. Kept
    # mid-sentence on purpose: en_core_web_sm tags a capitalised sentence-initial plural
    # as PROPN and then leaves its lemma uninflected, which would test the tagger's
    # quirks rather than these features.
    tier1 = client.post(
        "/api/v1/analyze",
        json={"mode": "single", "texts": ["The dogs barked and a dog barks."], "tiers": [1]},
    ).json()["results"][0]["features"]["tier1"]

    assert tier1["word_count"] == 7
    assert tier1["unique_word_count"] == 7
    assert tier1["unique_lemma_count"] == 5  # the, dog, bark, and, a


def test_lemma_count_tracks_word_count_on_prose(client):
    """Pinning the documented relationship, not an independent quantity.

    spaCy assigns one lemma per token, so `lemma_count` only differs from `word_count`
    where the lemmatizer returns a blank. If `lemma_forms` ever changes what it filters,
    this is the test that says so.
    """
    tier1 = client.post(
        "/api/v1/analyze",
        json={"mode": "single", "texts": [TEXT_A], "tiers": [1]},
    ).json()["results"][0]["features"]["tier1"]

    assert tier1["lemma_count"] == tier1["word_count"] == 11
    # Holds for any text: lemmatisation merges types, never splits them.
    assert tier1["unique_lemma_count"] <= tier1["unique_word_count"]


def test_word_densities_match_their_counts(client):
    tier1 = client.post(
        "/api/v1/analyze",
        json={"mode": "single", "texts": [TEXT_A], "tiers": [1]},
    ).json()["results"][0]["features"]["tier1"]

    assert tier1["content_word_density"] == pytest.approx(
        tier1["content_word_count"] / tier1["word_count"], abs=1e-4
    )
    assert tier1["function_word_density"] == pytest.approx(
        tier1["function_word_count"] / tier1["word_count"], abs=1e-4
    )
    # Content and function words partition the word tokens, so the densities complete.
    assert tier1["content_word_density"] + tier1["function_word_density"] == pytest.approx(
        1.0, abs=1e-4
    )


def test_densities_are_zero_when_a_text_has_no_words(client):
    """Punctuation-only input is the one way to reach the 0/0 case.

    Blank text is rejected at 422, so this is the reachable edge — and the answer must
    match `ttr`, which returns 0.0 for the same input rather than null.
    """
    tier1 = client.post(
        "/api/v1/analyze",
        json={"mode": "single", "texts": ["..."], "tiers": [1]},
    ).json()["results"][0]["features"]["tier1"]

    assert tier1["word_count"] == 0
    assert tier1["content_word_density"] == 0.0
    assert tier1["function_word_density"] == 0.0
    assert tier1["ttr"] == 0.0


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
