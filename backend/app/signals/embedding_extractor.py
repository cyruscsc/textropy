"""Embedding signals from `all-MiniLM-L6-v2` (spec §4).

Two signals share one model:

* `embedding.sentence_vectors` — one vector per spaCy sentence, plus a document vector.
* `embedding.word_vectors`     — one vector per content-word *type*, with corpus weights,
  for Word Mover's Distance.

Both declare `spacy.doc` as a dependency, so segmentation is the same parse Tier 1 uses
rather than a second tokenization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.models_ml import model_registry
from app.pipeline.context import AnalysisContext
from app.signals.base import (
    EMBEDDING_SENTENCE_VECTORS,
    EMBEDDING_WORD_VECTORS,
    SPACY_DOC,
    SignalExtractor,
)
from app.signals.spacy_extractor import CONTENT_POS


@dataclass(frozen=True)
class SentenceVectors:
    sentences: list[str]
    vectors: np.ndarray  # (n_sentences, dim), L2-normalised
    document_vector: np.ndarray  # (dim,), L2-normalised

    @property
    def count(self) -> int:
        return len(self.sentences)


@dataclass(frozen=True)
class WordVectors:
    """Type-level word vectors + normalised frequency weights.

    WMD is classically defined over static, type-level vectors (word2vec/GloVe), so each
    distinct content word is embedded once and weighted by its frequency in the text —
    rather than embedding every token occurrence in context.
    """

    types: list[str]
    vectors: np.ndarray  # (n_types, dim), L2-normalised
    weights: np.ndarray  # (n_types,), sums to 1


def _normalise(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    return matrix / np.clip(norms, 1e-12, None)


def _embedding_dim(embedder: Any) -> int:
    """Dimension of the embedder's output.

    sentence-transformers renamed `get_sentence_embedding_dimension` to
    `get_embedding_dimension`; support both so the pin can move either way.
    """
    getter = getattr(embedder, "get_embedding_dimension", None) or (
        embedder.get_sentence_embedding_dimension
    )
    return int(getter())


class SentenceVectorsExtractor(SignalExtractor):
    name = EMBEDDING_SENTENCE_VECTORS
    depends_on = (SPACY_DOC,)
    models = (model_registry.SENTENCE_EMBEDDER,)

    def extract(self, ctx: AnalysisContext) -> SentenceVectors:
        doc = ctx.get(SPACY_DOC)
        embedder = model_registry.get_model(model_registry.SENTENCE_EMBEDDER)

        sentences = [s.text.strip() for s in doc.sents if s.text.strip()]
        dim = _embedding_dim(embedder)

        if not sentences:
            return SentenceVectors(
                sentences=[],
                vectors=np.zeros((0, dim), dtype=np.float32),
                document_vector=np.zeros(dim, dtype=np.float32),
            )

        vectors = np.asarray(
            embedder.encode(sentences, convert_to_numpy=True, normalize_embeddings=True),
            dtype=np.float32,
        )
        # Document vector: mean of sentence vectors, renormalised. Cheaper than a second
        # encode() of the full text and consistent with the per-sentence view.
        document_vector = _normalise(vectors.mean(axis=0)).astype(np.float32)
        return SentenceVectors(
            sentences=sentences, vectors=vectors, document_vector=document_vector
        )


class WordVectorsExtractor(SignalExtractor):
    name = EMBEDDING_WORD_VECTORS
    depends_on = (SPACY_DOC,)
    models = (model_registry.SENTENCE_EMBEDDER,)

    def extract(self, ctx: AnalysisContext) -> WordVectors:
        doc: Any = ctx.get(SPACY_DOC)
        embedder = model_registry.get_model(model_registry.SENTENCE_EMBEDDER)
        dim = _embedding_dim(embedder)

        counts: dict[str, int] = {}
        for token in doc:
            if token.is_punct or token.is_space or token.is_stop:
                continue
            if token.pos_ not in CONTENT_POS:
                continue
            key = token.lemma_.lower() or token.text.lower()
            counts[key] = counts.get(key, 0) + 1

        if not counts:
            return WordVectors(
                types=[],
                vectors=np.zeros((0, dim), dtype=np.float32),
                weights=np.zeros(0, dtype=np.float64),
            )

        types = sorted(counts)
        vectors = np.asarray(
            embedder.encode(types, convert_to_numpy=True, normalize_embeddings=True),
            dtype=np.float32,
        )
        raw = np.asarray([counts[t] for t in types], dtype=np.float64)
        return WordVectors(types=types, vectors=vectors, weights=raw / raw.sum())
