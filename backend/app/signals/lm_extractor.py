"""`lm.token_logprobs` — per-token log-probabilities from DistilGPT2 (spec §3.1, Tier 3).

Also exposes `score_continuation`, the *cross-text* scoring primitive used by the Tier 3
comparison features. That is not a registered signal because it is not a property of a
single text: it scores text B with text A as the conditioning prefix.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.models_ml import model_registry
from app.models_ml.causal_lm import CausalLM
from app.pipeline.context import AnalysisContext
from app.signals.base import LM_TOKEN_LOGPROBS, SignalExtractor


@dataclass(frozen=True)
class TokenLogProbs:
    """Per-subword-token scores for one text.

    `logprobs[i]` is log P(token_i | token_<i) in **nats**. The first token has no
    conditioning context so its entry is None; `scored` skips it.
    """

    token_ids: list[int]
    offsets: list[tuple[int, int]]
    logprobs: list[float | None]
    truncated: bool = False

    @property
    def scored(self) -> list[float]:
        return [lp for lp in self.logprobs if lp is not None]

    def mean_logprob(self) -> float | None:
        scored = self.scored
        if not scored:
            return None
        return sum(scored) / len(scored)

    def perplexity(self) -> float | None:
        mean = self.mean_logprob()
        if mean is None:
            return None
        return math.exp(-mean)


def _encode(lm: CausalLM, text: str) -> tuple[list[int], list[tuple[int, int]], bool]:
    enc = lm.tokenizer(
        text,
        return_offsets_mapping=True,
        truncation=True,
        max_length=lm.max_length,
        add_special_tokens=False,
    )
    ids = list(enc["input_ids"])
    offsets = [(int(s), int(e)) for s, e in enc["offset_mapping"]]
    # `truncation=True` silently drops the tail; surface it so callers know the score
    # covers only a prefix of the text.
    truncated = len(ids) >= lm.max_length
    return ids, offsets, truncated


def _token_logprobs(lm: CausalLM, ids: list[int]) -> list[float]:
    """Return log P(ids[i] | ids[<i]) for i = 1..len(ids)-1 (length len(ids) - 1)."""
    import torch

    if len(ids) < 2:
        return []

    with torch.no_grad():
        input_ids = torch.tensor([ids], dtype=torch.long)
        logits = lm.model(input_ids=input_ids).logits
        log_probs = torch.log_softmax(logits[0, :-1, :].float(), dim=-1)
        targets = input_ids[0, 1:]
        picked = log_probs.gather(-1, targets.unsqueeze(-1)).squeeze(-1)
    return [float(x) for x in picked]


class LmTokenLogProbsExtractor(SignalExtractor):
    name = LM_TOKEN_LOGPROBS
    models = (model_registry.CAUSAL_LM,)

    def extract(self, ctx: AnalysisContext) -> TokenLogProbs:
        lm: CausalLM = model_registry.get_model(model_registry.CAUSAL_LM)
        ids, offsets, truncated = _encode(lm, ctx.text)
        scores = _token_logprobs(lm, ids)
        logprobs: list[float | None] = [None, *scores] if ids else []
        return TokenLogProbs(
            token_ids=ids,
            offsets=offsets,
            logprobs=logprobs,
            truncated=truncated,
        )


def score_continuation(context_text: str, continuation_text: str) -> TokenLogProbs:
    """Score `continuation_text` with `context_text` as the conditioning prefix.

    Every returned token belongs to the continuation, and — unlike the unconditional
    signal — its first token *is* scored, because the context supplies its history.
    Offsets are relative to `continuation_text`.
    """
    lm: CausalLM = model_registry.get_model(model_registry.CAUSAL_LM)

    ctx_ids, _, _ = _encode(lm, context_text)
    cont_ids, cont_offsets, truncated = _encode(lm, continuation_text)

    if not cont_ids:
        return TokenLogProbs(token_ids=[], offsets=[], logprobs=[], truncated=truncated)

    # Keep the newest context: budget = window minus the continuation we must score.
    budget = max(lm.max_length - len(cont_ids), 0)
    kept_ctx = ctx_ids[-budget:] if budget else []

    joint = [*kept_ctx, *cont_ids]
    scores = _token_logprobs(lm, joint)
    # scores[i] corresponds to joint[i + 1]; the continuation starts at joint index
    # len(kept_ctx), i.e. scores index len(kept_ctx) - 1.
    start = len(kept_ctx) - 1
    if start < 0:
        # No context survived the budget: fall back to the unconditional first token.
        cont_scores: list[float | None] = [None, *scores]
    else:
        cont_scores = list(scores[start : start + len(cont_ids)])

    # Guard against any off-by-one from truncation edge cases.
    cont_scores = cont_scores[: len(cont_ids)]
    while len(cont_scores) < len(cont_ids):
        cont_scores.append(None)

    return TokenLogProbs(
        token_ids=cont_ids,
        offsets=cont_offsets,
        logprobs=cont_scores,
        truncated=truncated or len(kept_ctx) < len(ctx_ids),
    )
