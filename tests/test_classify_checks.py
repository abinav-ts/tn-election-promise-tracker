"""Spec 03 §7: checks C1–C6."""

import pytest

from ept.classify.checks import (Limits, Subject, check_c2, check_c3, check_c4, check_c5, check_c6, match_results,
                                 parse_override)
from ept.classify.rubric import PromiseOut

LIM = Limits(2, 4, 2, 4, 2, 12, 40, frozenset({"Union", "Government", "Rs"}))
SUBJ = Subject(text="Provide Rs 2,000 a month to fishers in Ramanathapuram during the ban period.",
               source_text="Fishers in Ramanathapuram will get Rs 2,000 a month during the ban period.",
               source_lang="en", section="Fisheries Welfare",
               unit_text="12. Fisheries Welfare\nFishers in Ramanathapuram will get Rs 2,000 a month during the ban "
                         "period. The ‘Sea Guard’ relief will be continued.")


def _r(**kw) -> PromiseOut:
    base = dict(promise_id="P01", sector="agriculture_fisheries", promise_type="transfer_subsidy",
                specificity="specific", cost_band="medium", union_dependent=False, union_basis="none",
                continues_existing=False, continues_cue="", headline_signal=0,
                search_queries=["fishers ban period assistance", "Rs 2,000 monthly fishers Ramanathapuram"])
    base.update(kw)
    return PromiseOut.model_validate(base)


def _vague(indicators, **kw):
    return _r(specificity="vague", search_queries=[], indicators=indicators, **kw)


# --- C1 -------------------------------------------------------------------------

def test_c1_matched_by_id_shuffled_batch_passes():
    a, b, c = _r(promise_id="P01"), _r(promise_id="P02"), _r(promise_id="P03")
    matched, fails, extras = match_results(["P01", "P02", "P03"], [c, a, b])
    assert matched == {"P01": a, "P02": b, "P03": c} and not fails and not extras


def test_c1_missing_duplicate_and_extra_ids():
    a = _r(promise_id="P01")
    matched, fails, extras = match_results(["P01", "P02", "P03"], [a, _r(promise_id="P03"), _r(promise_id="P03"),
                                                                   _r(promise_id="P09")])
    assert list(matched) == ["P01"]
    assert fails["P02"].startswith("C1: no result") and fails["P03"].startswith("C1: 2 results")
    assert extras == ["P09"]


def test_c1_override_parsed_through_the_output_model():
    row = {"sector": "health", "promise_type": "infrastructure", "specificity": "specific", "cost_band": "low",
           "union_dependent": "false", "union_basis": "none", "continues_existing": "false", "continues_cue": "",
           "headline_signal": "0", "indicators_json": '{"search_queries": ["a b", "c d"]}'}
    r, fails = parse_override(row, "P01")
    assert r is not None and not fails and r.search_queries == ["a b", "c d"]
    r, fails = parse_override(dict(row, sector="sports"), "P01")
    assert r is None and fails[0].startswith("C1")
    r, fails = parse_override(dict(row, union_dependent="maybe"), "P01")
    assert r is None and fails[0].startswith("C1")


# --- C2 -------------------------------------------------------------------------

def test_c2_specific_and_vague():
    assert check_c2(_r(), LIM) == []
    assert check_c2(_r(search_queries=["a b"]), LIM)  # 1 query
    assert check_c2(_r(indicators=[{"text": "x", "search_queries": ["a b", "c d"]}]), LIM)
    ok = [{"text": "An order is issued.", "search_queries": ["a b", "c d"]}] * 2
    assert check_c2(_vague(ok), LIM) == []
    assert check_c2(_vague(ok[:1]), LIM)  # 1 indicator
    assert check_c2(_vague(ok * 3), LIM)  # 6 indicators
    assert check_c2(_vague([ok[0], {"text": "x", "search_queries": ["a b"]}]), LIM)


# --- C3 -------------------------------------------------------------------------

def test_c3_number_not_in_text_fails():
    assert check_c3(_r(search_queries=["fishers ban period relief", "Rs 5,000 fishers relief"]), SUBJ, LIM)
    assert check_c3(_r(search_queries=["fishers ban period relief", "fishers relief 2021 order"]), SUBJ, LIM)
    assert check_c3(_r(search_queries=["fishers relief rs 2000", "fishers ban period"]), SUBJ, LIM) == []


def test_c3_capitalised_name_not_in_text_fails_common_words_pass():
    bad = _r(search_queries=["fishers ban period relief", "Amma fishers relief scheme"])
    assert "Amma" in check_c3(bad, SUBJ, LIM)[0]
    ok = _r(search_queries=["Union Government fishers relief", "Ramanathapuram fishers ban relief"])
    assert check_c3(ok, SUBJ, LIM) == []


def test_c3_query_has_no_sentence_initial_exemption_indicator_has():
    assert check_c3(_r(search_queries=["Kalaignar fishers relief", "fishers ban period"]), SUBJ, LIM)
    ind = [{"text": "Payments start for fishers.", "search_queries": ["fishers payment start", "ban period relief"]},
           {"text": "An order on Kalaignar relief is issued.", "search_queries": ["fishers relief order", "a b"]}]
    fails = check_c3(_vague(ind), SUBJ, LIM)
    assert len(fails) == 1 and "indicator 2" in fails[0] and "Kalaignar" in fails[0]


def test_c3_lower_case_query_words_pass_and_section_counts():
    assert check_c3(_r(search_queries=["kalaignar fishers relief", "Fisheries Welfare department order"]),
                    SUBJ, LIM) == []


def test_c3_tamil_source_text_is_not_a_name_source():
    ta = Subject(text="Provide relief to fishers.", source_text="Mannar fishers", source_lang="ta", section=None,
                 unit_text="Mannar fishers")
    assert check_c3(_r(search_queries=["fishers relief order", "Mannar fishers relief"]), ta, LIM)
    en = Subject(text="Provide relief to fishers.", source_text="Mannar fishers", source_lang="en", section=None,
                 unit_text="Mannar fishers")
    assert check_c3(_r(search_queries=["fishers relief order", "Mannar fishers relief"]), en, LIM) == []


def test_c3_names_from_sibling_promises_and_acronyms_pass():
    from dataclasses import replace

    sub = replace(SUBJ, text="Take legal action to secure the river water due to the state.",
                  unit_promise_texts=("Secure the due share of Cauvery water.",
                                      "Oppose the New Education Policy of the Union Government."))
    ok = _r(search_queries=["Cauvery water legal action", "NEP opposition resolution"])
    assert check_c3(ok, sub, LIM) == []
    assert check_c3(_r(search_queries=["Vaigai water legal action", "river water order"]), sub, LIM)
    assert check_c3(_r(search_queries=["NEPS opposition", "XYZ water order"]), sub, LIM)  # XYZ fails
    assert check_c3(_r(search_queries=["river water 2018 verdict", "river water order"]), sub, LIM)  # numbers stay strict


def test_acronyms():
    from ept.classify.checks import acronyms

    assert {"MHA", "TN", "TNPSC"} <= acronyms("the Ministry of Home Affairs and the Tamil Nadu Public Service Commission")
    assert "NEP" in acronyms("Union government's New Education Policy")


# --- C4 -------------------------------------------------------------------------

def test_c4_cue_verbatim_with_quote_and_nfc_normalisation():
    ok = _r(continues_existing=True, continues_cue="The 'Sea Guard' relief will be  continued")
    assert check_c4(ok, SUBJ) == []
    assert check_c4(_r(continues_existing=True, continues_cue="the scheme will continue"), SUBJ)
    assert check_c4(_r(continues_existing=True, continues_cue=""), SUBJ)
    assert check_c4(_r(continues_existing=False, continues_cue="will be continued"), SUBJ)
    nfc = Subject(text="Do x.", source_text="x", source_lang="ta", section=None, unit_text="திட்டம் தொடரும்")
    decomposed = "திட்டம் தொடரும்".replace("ொ", "ெ" + "ா")  # NFD-style two-part vowel sign
    assert check_c4(_r(continues_existing=True, continues_cue=decomposed), nfc) == []


def test_c4_union_basis_matches_flag():
    assert check_c4(_r(union_dependent=True, union_basis="none"), SUBJ)
    assert check_c4(_r(union_dependent=False, union_basis="union_funds"), SUBJ)
    assert check_c4(_r(union_dependent=True, union_basis="union_funds"), SUBJ) == []


# --- C5, C6 -----------------------------------------------------------------------

def test_c5_consistency():
    assert check_c5(_r(promise_type="advocacy", union_dependent=True, union_basis="union_subject"))
    assert check_c5(_r(promise_type="advocacy", union_dependent=True, union_basis="advocacy")) == []
    assert check_c5(_r(promise_type="scheme_expansion"))
    assert check_c5(_r(promise_type="scheme_expansion", continues_existing=True, continues_cue="x")) == []


def test_c6_limits():
    assert check_c6(_r(), SUBJ, LIM) == []
    assert check_c6(_r(headline_signal=2), SUBJ, LIM) == []
    assert check_c6(_r(headline_signal=3), SUBJ, LIM)  # 0–2 since the front-matter point was dropped
    assert check_c6(_r(headline_signal=-1), SUBJ, LIM)
    assert check_c6(_r(search_queries=["fishers", "fishers ban period"]), SUBJ, LIM)  # 1 word
    assert check_c6(_r(search_queries=["fishers " * 13, "fishers ban period"]), SUBJ, LIM)
    long = [{"text": "word " * 41, "search_queries": ["a b", "c d"]}, {"text": "x", "search_queries": ["a b", "c d"]}]
    assert check_c6(_vague(long), SUBJ, LIM)


def test_c6_self_indicator_is_exempt_from_the_word_limit():
    long = Subject(text="Provide " + "relief " * 50, source_text="x", source_lang="en", section=None, unit_text="x")
    assert check_c6(_r(search_queries=["relief order", "relief scheme"]), long, LIM) == []
