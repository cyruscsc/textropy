"""Request models (spec §6)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

Tier = Annotated[int, Field(ge=1, le=3)]


class AnalyzeRequest(BaseModel):
    mode: Literal["single", "compare"] = "single"
    texts: list[str] = Field(min_length=1, max_length=2)
    tiers: list[Tier] = Field(default=[1])
    feature_names: list[str] | None = None

    @model_validator(mode="after")
    def _check(self) -> AnalyzeRequest:
        expected = 1 if self.mode == "single" else 2
        if len(self.texts) != expected:
            raise ValueError(
                f"mode={self.mode!r} requires exactly {expected} text(s), got {len(self.texts)}"
            )
        if any(not text.strip() for text in self.texts):
            raise ValueError("texts must not be empty or whitespace-only")
        if not self.tiers and self.feature_names is None:
            raise ValueError("provide at least one tier, or an explicit feature_names list")

        # Deduplicate while keeping the caller's order stable in the response.
        self.tiers = sorted(set(self.tiers))
        return self
