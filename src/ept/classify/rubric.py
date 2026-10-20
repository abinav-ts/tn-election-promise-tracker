"""Covariate rubric (spec 03 §4.2) and the model's output shape (§4.3).

The §7 covariate values (`Sector`, `PromiseType`, `CostBand`) live in `ept.schema`; the audit
values (`UnionBasis`) are stage 03 artefacts (D-069) and live here. The definitions are written
out in prompts/classify_promises.md; one prompt version covers rubric and prompt.
"""

from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict

from ept.schema import COST_BANDS, PROMISE_TYPES, SECTORS, CostBand, PromiseType, Sector

PROMPT = "classify_promises"

UnionBasis = Literal["advocacy", "union_subject", "presidential_assent", "union_approval", "union_funds",
                     "gst_council", "none"]
UNION_BASES: tuple[str, ...] = get_args(UnionBasis)
SPECIFICITIES = ("specific", "vague")
HEADLINE_SIGNAL_MAX = 2  # one point per signal, two signals (§4.5; the front-matter point was dropped, D-072)

COVARIATES = ("sector", "promise_type", "specificity", "cost_band", "union_dependent", "continues_existing",
              "headline", "covariates_version")
AUDIT_FIELDS = ("union_basis", "continues_cue", "headline_signal", "headline_rank")

__all__ = ["COST_BANDS", "PROMISE_TYPES", "SECTORS", "CostBand", "PromiseType", "Sector"]


def covariates_version(prompt_version: str) -> str:
    return f"{PROMPT} v{prompt_version}"


class IndicatorOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    search_queries: list[str]


class PromiseOut(BaseModel):
    """One promise's answer. `promise_id` is the batch-local alias the prompt used (P01, P02, …)."""

    model_config = ConfigDict(extra="forbid")

    promise_id: str
    sector: Sector
    promise_type: PromiseType
    specificity: Literal["specific", "vague"]
    cost_band: CostBand
    union_dependent: bool
    union_basis: UnionBasis
    continues_existing: bool
    continues_cue: str
    headline_signal: int
    search_queries: list[str] = []  # specific: queries for the self indicator
    indicators: list[IndicatorOut] = []  # vague: 2–4 indicators


class ClassifyOut(BaseModel):
    promises: list[PromiseOut]
