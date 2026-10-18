"""Spec 03 §7: rubric enums match §4.2; schema accepts every value and rejects others."""

import re

import pytest
from pydantic import ValidationError

from conftest import REPO

SECTORS = ["agriculture_fisheries", "education", "health", "social_welfare", "caste_minority_welfare",
           "employment_labour", "industry_it_msme", "infrastructure_transport_housing", "local_government",
           "water_environment_energy", "governance_law_state_rights", "culture_language_religion", "other"]
TYPES = ["advocacy", "law_regulation", "transfer_subsidy", "infrastructure", "institution", "scheme_expansion",
         "new_scheme", "administrative"]
BANDS = ["none", "low", "medium", "high"]
BASES = ["advocacy", "union_subject", "presidential_assent", "union_approval", "union_funds", "gst_council", "none"]


def _promise(**kw):
    from ept.schema import Promise

    return Promise(promise_id="DMK-2021-0001", term_id="DMK-2021", text="Do x.", source_text="x", source_lang="en",
                   **kw)


def test_enums_match_spec():
    from ept.classify import rubric
    from ept import schema

    assert list(schema.SECTORS) == SECTORS
    assert list(schema.PROMISE_TYPES) == TYPES  # precedence order
    assert list(schema.COST_BANDS) == BANDS
    assert list(rubric.UNION_BASES) == BASES


@pytest.mark.parametrize("field,values", [("sector", SECTORS), ("promise_type", TYPES), ("cost_band", BANDS)])
def test_schema_accepts_every_value_and_rejects_others(field, values):
    for v in values:
        assert getattr(_promise(**{field: v}), field) == v
    with pytest.raises(ValidationError):
        _promise(**{field: "not_a_value"})
    assert getattr(_promise(), field) is None  # null until classified


def test_prompt_names_every_value_in_order():
    body = (REPO / "prompts" / "classify_promises.md").read_text(encoding="utf-8")
    for v in SECTORS + BASES + BANDS:
        assert f"`{v}`" in body, v
    positions = [body.index(f"`{t}`:") for t in TYPES]
    assert positions == sorted(positions)


def test_covariates_version_format():
    from ept.classify.rubric import covariates_version
    from ept.llm import load_prompt
    from ept.config import load_config

    v = load_prompt("classify_promises", load_config(REPO)).version
    assert re.fullmatch(r"classify_promises v\d+\.\d+", covariates_version(v))
