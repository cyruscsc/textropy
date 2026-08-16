"""`spacy.doc` — the shared parse every Tier 1 feature reads (spec §3.1)."""

from __future__ import annotations

from typing import Any

from app.models_ml import model_registry
from app.pipeline.context import AnalysisContext
from app.signals.base import SPACY_DOC, SignalExtractor


class SpacyDocExtractor(SignalExtractor):
    name = SPACY_DOC
    models = (model_registry.SPACY,)

    def extract(self, ctx: AnalysisContext) -> Any:
        nlp = model_registry.get_model(model_registry.SPACY)
        return nlp(ctx.text)


def word_tokens(doc: Any) -> list[Any]:
    """Tokens that count as words: punctuation and whitespace excluded.

    Shared by every lexical feature and by n-gram overlap so that "word count" means the
    same thing everywhere in the API.
    """
    return [t for t in doc if not t.is_punct and not t.is_space]


def content_sentences(doc: Any) -> list[Any]:
    """Sentence spans holding at least one word token.

    A span of only punctuation or whitespace is not a sentence for counting purposes — `"..."`
    parses as exactly one such span. Excluding them keeps `sentence_count` honest and keeps
    every per-sentence series (lengths, MDD, tree depth) over the same set of sentences.

    Lives here rather than in a feature module because both `tier1/sentence.py` and
    `tier1/complexity.py` build series from it, and one definition of "a sentence" is what
    stops those two groups from describing different populations.
    """
    return [sent for sent in doc.sents if word_tokens(sent)]


# Universal POS tags treated as content-bearing (spec §3.1: content vs function words).
CONTENT_POS = frozenset({"NOUN", "PROPN", "VERB", "ADJ", "ADV"})
