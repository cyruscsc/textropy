"""Pass 1 base class and canonical signal names (spec §4)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from app.pipeline.context import AnalysisContext

# --- Canonical signal names -----------------------------------------------------
# Referenced by feature/comparison computers in their `requires` tuples. Keeping them as
# constants means a typo is an ImportError, not a silently-missing signal at runtime.
SPACY_DOC = "spacy.doc"
LM_TOKEN_LOGPROBS = "lm.token_logprobs"
EMBEDDING_SENTENCE_VECTORS = "embedding.sentence_vectors"
EMBEDDING_WORD_VECTORS = "embedding.word_vectors"
ALIGNMENT_LM_TO_SPACY = "alignment.lm_to_spacy"
SENTIMENT_DOCUMENT = "sentiment.document"
COREF_CLUSTERS = "coref.clusters"


class SignalExtractor(ABC):
    """Extracts one fundamental signal from one text.

    Extractors may depend on other *signals* (`depends_on`) and on loaded *models*
    (`models`). The orchestrator resolves `depends_on` into a topological run order, so an
    extractor can assume every signal it declared is already present on the context.
    """

    name: ClassVar[str]
    depends_on: ClassVar[tuple[str, ...]] = ()
    models: ClassVar[tuple[str, ...]] = ()

    @abstractmethod
    def extract(self, ctx: AnalysisContext) -> Any:
        """Compute the signal. The orchestrator stores the return value on the context."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} {self.name}>"
