"""Orchestration and output (spec 07 §4.7): runs KM, Cox, the reverse backtest and the projection, writes the report,
the site export and the figures."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from ept.config import Config
from ept.model import backtest, data, km, project
from ept.model.cox import fit_cox

LIMITATIONS = [
    "The judge differs by term and month: month-5 realised share is 4.8 % for DMK-2021 and 3.3 % for TVK-2026 "
    "(both Claude-judged) against 34.6 % for AIADMK-2016 (Gemini-judged); from month 24 both completed terms are "
    "mostly Gemini-judged and AIADMK is still 20-25 points higher. The backtest measures model error plus some judge "
    "difference (stage 06 bounds it); no parameter is adjusted for it.",
    "Only two completed terms, treated as independent draws. The reverse backtest is cross-term validation, "
    "not a forecast; the forward direction was not built, so the AIADMK-only model is not validated as a predictor.",
    "Year- and month-precision dates (about 16 % of events) and conservative document dates blur event times.",
    "`unverifiable` is censored, not an event; it is 124 of TVK's 695 promises.",
    "Realisation dates are approximate: against 40 hand-labelled promises (stage 06) the median gap is about five to six months and fewer than a third are within 90 days, so the timing in these curves and in the backtest is blurred.",
    "Five covariates leave most variation unexplained; the bootstrap band shows fitting uncertainty only.",
    "TVK starts with a different coalition, Union-State relationship and fiscal position; the projection is "
    "'projection under historical patterns' and extrapolates from month 5.",
]


SCENARIO_TEXT = """### How to read the three TVK lines (assumptions)

- **no update.** Assumes TVK will realise promises at the *average historical pace of the two completed terms*, whatever happened in its first five months.
- **Scenario A, pace update, pre-specified (k = {kA:.2f}).** Assumes the average of the completed terms predicts how many promises should have been realised by month 5, and that TVK's relative speed since then continues. Its weakness: the expectation comes from *hindsight* event dates (promises later found realised early), while TVK's 3.3 % counts only what is documented now. Part of the apparent slowness is therefore documentation lag, not slow delivery.
- **Scenario B, judge-matched pace update (k = {kB:.2f}), added after seeing scenario A (D-114).** Assumes TVK's month-5 count should be compared with the *documented* month-5 share of terms judged by the same judge at the same landmark ({matched}: {share}), so it compares like with like. Its weakness: it was chosen after seeing A's result, it rests on one term, and its k is then applied to hindsight-based hazards.
- All three are 'projection under historical patterns'. The bands show fitting uncertainty only."""


def _fits(cfg: Config, tbl: pd.DataFrame) -> dict:
    m = cfg.settings.model
    out = {}
    for name, terms, strata in [("DMK-2021", ["DMK-2021"], None), ("AIADMK-2016", ["AIADMK-2016"], None),
                                ("both_terms_strata", ["DMK-2021", "AIADMK-2016"], "term_id")]:
        d = tbl[tbl.term_id.isin(terms)]
        f = fit_cox(d, m.covariates, m.reference, terms, strata=strata)
        entry = {"n": int(len(d)), "events": int(d["E1"].sum()),
                 "hazard_ratios": f.hazard_ratios().round(4).reset_index().to_dict("records")}
        try:
            from lifelines.statistics import proportional_hazard_test
            frame = f.X(d).assign(T=d["T"].values, E=d["E1"].values)
            if strata:
                frame[strata] = d[strata].values
            ph = proportional_hazard_test(f.model, frame, time_transform="rank")
            entry["schoenfeld_p"] = {k: float(v) for k, v in ph.summary["p"].items()}
        except Exception as e:  # reported, never fatal
            entry["schoenfeld_p"] = {"error": str(e)[:120]}
        out[name] = entry
    return out


def run_all(cfg: Config, quick: bool = False) -> dict:
    m = cfg.settings.model
    rows = data.load_final(cfg)
    tbl = data.analysis_table(cfg, rows=rows)
    if quick:
        cfg.settings.model.bootstrap.n = min(cfg.settings.model.bootstrap.n, 20)
    res: dict = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                 "final_export": data.newest_final(cfg).name, "settings": m.model_dump(mode="json"),
                 "counts": {t: {"n": int(len(d)), "E1": int(d["E1"].sum()), "E2": int(d["E2"].sum()),
                                "day1": int((d[d.E1 == 1]["T"] == 1).sum()),
                                "coarse_dates": int(((d.E1 == 1) & (d.date_precision != "day")).sum()),
                                "unverifiable": int((d.status == "unverifiable").sum())}
                            for t, d in tbl.groupby("term_id")},
                 "judge_sources": data.judge_source_table(cfg, rows), "limitations": LIMITATIONS}
    res["km"] = km.km_tables(cfg, tbl)
    res["cox"] = _fits(cfg, tbl)
    res["backtest"] = {"E1": backtest.reverse_backtest(cfg, tbl, rows, "DMK-2021", "AIADMK-2016", "E1"),
                       "E2": backtest.reverse_backtest(cfg, tbl, rows, "DMK-2021", "AIADMK-2016", "E2")}
    sens = {}
    for mode in ("start", "end"):
        t2 = data.analysis_table(cfg, mode=mode, rows=rows)
        b = backtest.reverse_backtest(cfg, t2, rows, "DMK-2021", "AIADMK-2016", "E1")
        sens[mode] = {lm: {k: e[k] for k in ("mae_model", "mae_model_pace", "mae_baseline")}
                      for lm, e in b["landmarks"].items()}
    res["backtest_date_sensitivity"] = sens
    res["projection"] = project.project(cfg, tbl, "E1", rows)
    return res


def _pct(x) -> str:
    return f"{100 * x:.1f}%"


def write_markdown(cfg: Config, res: dict, path: Path) -> None:
    L = ["# Stage 07 — Survival modelling report", "",
         f"Generated {res['generated_at']} · final verdicts `{res['final_export']}`", "",
         "## Counts (E1 = fulfilled, partial or diluted with a date)", "",
         "| term | promises | E1 events | E2 events | events on day 1 | coarse dates | unverifiable (censored) |", "|---|---|---|---|---|---|---|"]
    for t, c in res["counts"].items():
        L.append(f"| {t} | {c['n']} | {c['E1']} | {c['E2']} | {c['day1']} | {c['coarse_dates']} | {c['unverifiable']} |")
    L += ["", "## Judge source of the final verdicts (read every cross-term comparison with this)", "",
          "| term | cutoff | bulk | strong | human | n |", "|---|---|---|---|---|---|"]
    for r in res["judge_sources"]:
        L.append(f"| {r['term']} | {r['cutoff']} | {r.get('bulk', 0)} | {r.get('strong', 0)} | {r.get('human', 0)} | {r['n']} |")
    L += ["", "## Share realised by month (Kaplan-Meier, E1, 95% interval)", "",
          "| term | " + " | ".join(f"m{x}" for x in res["km"]["months"]) + " |", "|---|" + "---|" * len(res["km"]["months"])]
    for t, e in res["km"]["terms"].items():
        cells = [f"{_pct(e['E1']['realised'][e['months'].index(x)])} ({_pct(e['E1']['lo'][e['months'].index(x)])}-{_pct(e['E1']['hi'][e['months'].index(x)])})"
                 if x in e["months"] else "–" for x in res["km"]["months"]]
        L.append(f"| {t} | " + " | ".join(cells) + " |")
    L += ["", "## Cox hazard ratios (E1; above 1 = realised faster)", ""]
    for name, e in res["cox"].items():
        L += [f"**{name}** (n={e['n']}, events={e['events']})", "", "| covariate | HR | 95% CI | p | Schoenfeld p |", "|---|---|---|---|---|"]
        for r in e["hazard_ratios"]:
            sp = e["schoenfeld_p"].get(r["covariate"])
            L.append(f"| {r['covariate']} | {r['hr']:.2f} | {r['lo']:.2f}-{r['hi']:.2f} | {r['p']:.3f} | {'' if sp is None else f'{sp:.3f}'} |")
        L.append("")
    b = res["backtest"]["E1"]
    L += [f"## Reverse backtest: fit on {b['train']} only, predict {b['target']} (E1)", "",
          f"Concordance of the DMK model on AIADMK full-term data: **{b['concordance']:.3f}** (0.5 = no better than chance). "
          f"Rows with a covariate level unseen in training: {b['unseen_level_rows']}.", "",
          "Mean absolute error of the predicted share realised, in percentage points, over later months:", "",
          "| landmark | realised at landmark | model expected | pace factor k | model | model + pace update | no-covariate baseline |",
          "|---|---|---|---|---|---|---|"]
    kk = f"k_c={cfg.settings.model.pace_prior_events}"
    for lm, e in b["landmarks"].items():
        L.append(f"| m{lm} | {e['realised_at_landmark']} | {e['expected']:.0f} | {e[kk]:.2f} | {e['mae_model']:.1f} | {e['mae_model_pace']:.1f} | {e['mae_baseline']:.1f} |")
    L += ["", "Predicted vs observed share at selected months (model + pace update):", "",
          "| landmark | month | predicted | no update | observed |", "|---|---|---|---|---|"]
    for lm, e in b["landmarks"].items():
        for t in (12, 24, 36, 48, 60):
            if t in e["t_months"]:
                i = e["t_months"].index(t)
                L.append(f"| m{lm} | {t} | {_pct(e['pred_model_pace'][i])} | {_pct(e['pred_model'][i])} | {_pct(e['observed'][i])} |")
    L += ["", "Sensitivity (MAE, model + pace update; E1 dates at period start / end): " +
          "; ".join(f"{mode}: " + ", ".join(f"m{lm} {v['mae_model_pace']:.1f}" for lm, v in d.items())
                    for mode, d in res["backtest_date_sensitivity"].items()), ""]
    e2 = res["backtest"]["E2"]
    L += ["E2 (fulfilled only) MAE, model + pace update: " + ", ".join(f"m{lm} {e['mae_model_pace']:.1f}" for lm, e in e2["landmarks"].items()), ""]
    p = res["projection"]
    L += ["## TVK-2026 projection (pooled two-term model, equal-weight baselines)", "",
          f"Snapshot day {p['snapshot_day']} (month 5): {p['observed_events']} of {p['n']} promises realised "
          f"({_pct(p['observed_share_snapshot'])}). Bootstrap: {p['bootstrap']['n_ok']} of {p['bootstrap']['n_requested']} resamples fitted; band = "
          f"{int(p['bootstrap']['band'][0]*100)}th-{int(p['bootstrap']['band'][1]*100)}th percentile (fitting uncertainty only).", "",
          "| variant | k | expected by month 5 | m6 | m12 | m24 | m36 | m48 | m60 |", "|---|---|---|---|---|---|---|---|---|"]
    for label in ("no_update", "pace_update", "matched_update",
                  *[k for k in p if k.startswith(("pace_update_c", "matched_update_c"))]):
        if label not in p:
            continue
        r = p[label]
        cells = [_pct(r["share"][p["months"].index(x)]) for x in (6, 12, 24, 36, 48, 60)]
        L.append(f"| {label} | {r['k']:.3f} | {r['expected']:.0f} | " + " | ".join(cells) + " |")
    for label in ("no_update", "pace_update", "matched_update"):
        if label in p and "lo" in p[label]:
            idx = [p["months"].index(x) for x in (6, 12, 24, 36, 48, 60)]
            L.append(f"| {label} band | | | " + " | ".join(f"{_pct(p[label]['lo'][i])}-{_pct(p[label]['hi'][i])}" for i in idx) + " |")
    L += ["", SCENARIO_TEXT.format(matched=", ".join(p.get("matched", {}).get("terms", [])) or "none",
                                    share=_pct(p.get("matched", {}).get("documented_share_month5", float("nan"))),
                                    kA=p["pace_update"]["k"], kB=p.get("matched_update", {}).get("k", float("nan")))]
    L += ["", "## Limitations", ""] + [f"{i}. {t}" for i, t in enumerate(res["limitations"], 1)] + [""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L), encoding="utf-8")


def write_outputs(cfg: Config, res: dict) -> dict:
    jp, mp, op = cfg.path("model_report_json"), cfg.path("model_report_md"), cfg.path("model_outputs")
    for p in (jp, op):
        p.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps(res, indent=1), encoding="utf-8")
    site = {"generated_at": res["generated_at"], "km": res["km"], "cox": res["cox"],
            "backtest": res["backtest"]["E1"], "projection": res["projection"], "limitations": res["limitations"],
            "judge_sources": res["judge_sources"]}
    op.write_text(json.dumps(site), encoding="utf-8")
    write_markdown(cfg, res, mp)
    _figures(cfg, res)
    return {"report": str(mp), "json": str(jp), "site": str(op)}


def _figures(cfg: Config, res: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d = cfg.path("model_figures")
    d.mkdir(parents=True, exist_ok=True)
    p = res["projection"]
    fig, ax = plt.subplots(figsize=(7, 4))
    x = p["months"]
    for label, color in (("no_update", "#7a8a99"), ("pace_update", "#1f6b52"), ("matched_update", "#a35a1f")):
        if label not in p:
            continue
        ax.plot(x, [100 * v for v in p[label]["share"]], color=color, label=label.replace("_", " "))
        if "lo" in p[label]:
            ax.fill_between(x, [100 * v for v in p[label]["lo"]], [100 * v for v in p[label]["hi"]], color=color, alpha=0.15)
    ax.set_xlabel("month of tenure"); ax.set_ylabel("% of TVK promises realised"); ax.legend(); ax.set_title("TVK-2026 projection (historical patterns)")
    fig.tight_layout(); fig.savefig(d / "projection.png", dpi=150); plt.close(fig)
    b = res["backtest"]["E1"]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(b["months"], [100 * v for v in b["observed"]], color="black", label="AIADMK observed")
    for lm in ("5", "12", "24"):
        e = b["landmarks"][lm]
        ax.plot(e["t_months"], [100 * v for v in e["pred_model_pace"]], label=f"predicted from m{lm} (pace update)")
    ax.set_xlabel("month of tenure"); ax.set_ylabel("% realised"); ax.legend(); ax.set_title("Reverse backtest (DMK model, AIADMK target)")
    fig.tight_layout(); fig.savefig(d / "backtest.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    for t, e in res["km"]["terms"].items():
        ax.step([0] + e["months"], [0] + [100 * v for v in e["E1"]["realised"]], where="post", label=t)
    ax.set_xlabel("month of tenure"); ax.set_ylabel("% realised (E1)"); ax.legend(); ax.set_title("Kaplan-Meier by term")
    fig.tight_layout(); fig.savefig(d / "km_terms.png", dpi=150); plt.close(fig)
