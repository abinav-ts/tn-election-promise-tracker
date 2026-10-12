"""`ept extract backend-test` (spec 02 §4.8, D-053): choose the bulk model on a fixed sample.

Sample: `extract.backend_test.per_term` units per term (10 DMK + 10 AIADMK), drawn with a
seeded RNG, never used as few-shot examples. Each candidate in `llm.bulk.candidates`
extracts the sample in the production call shape (batches of `units_per_call`).
Measures: JSON valid first time, V1/V2/V3 pass rates over the promises returned,
promises per unit, seconds per call, HTTP 429/5xx backoffs. Rule: the highest V1 pass
rate wins, ties to the larger daily quota; if none reaches `llm.bulk.min_v1_pass`, stop
and ask the user. `--smoke` = one live call with no project data (step 3).
"""

from __future__ import annotations

import datetime as dt
import json
import random
import re
from typing import Any, Optional

from pydantic import BaseModel

from ept.config import Config, get_config
from ept.extract.checks import check_promise
from ept.extract.units import Unit, read_units
from ept.extract.promises import call_batch
from ept.llm import LLMClient, LLMValidationError, QuotaExhausted
from ept.runs import finish_run, start_run


class SmokeOut(BaseModel):
    ok: bool
    echo: str


def run_smoke(model: Optional[str] = None) -> dict[str, Any]:
    """One live call (cached afterwards) with no project data: checks key, model name, JSON mode."""
    cfg = get_config()
    model = model or cfg.settings.llm.models.get("vision")
    client = LLMClient(cfg)
    out = client.complete_json("smoke_test", {"word": "vanakkam"}, SmokeOut, model=model)
    return {"model": model, "ok": out.ok and out.echo == "vanakkam", "cache_hit": client.last.cache_hit,
            "seconds": client.last.seconds, "http_retries": client.last.http_retries}


def draw_sample(cfg: Config) -> dict[str, list[Unit]]:
    bt = cfg.settings.extract.backend_test
    rng = random.Random(bt.seed)
    out = {}
    for term, k in bt.per_term.items():
        units = read_units(cfg, term)
        if len(units) < k:
            raise RuntimeError(f"{term}: {len(units)} units, the sample needs {k} (run `extract units`)")
        picked = sorted(rng.sample(range(len(units)), k))
        out[term] = [units[i] for i in picked]
    return out


def evaluate(cfg: Config, client: LLMClient, model: str, sample: dict[str, list[Unit]]) -> dict[str, Any]:
    profiles = cfg.profiles()
    ex = cfg.settings.extract
    calls = json_first = http = 0
    seconds = 0.0
    promises = v1 = v2 = v3 = 0
    per_term: dict[str, Any] = {}
    missing = 0
    for term, units in sample.items():
        t_prom = t_v1 = 0
        for b in range(0, len(units), ex.units_per_call):
            batch = units[b:b + ex.units_per_call]
            try:
                outs = call_batch(client, term, profiles[term], batch, model=model)
                json_first += client.last.first_valid
            except LLMValidationError:
                outs = {}
            calls += 1
            seconds += client.last.seconds
            http += client.last.http_retries
            for u in batch:
                o = outs.get(u.unit_id)
                if o is None:
                    missing += 1
                    continue
                for p in o.pieces:
                    if p.kind != "promise":
                        continue
                    r = check_promise(p.text, p.source_text, u.text, profiles[term].lang,
                                      common_words=set(ex.common_words), max_words=ex.max_text_words)
                    promises += 1
                    t_prom += 1
                    v1 += r.passed("V1")
                    t_v1 += r.passed("V1")
                    v2 += r.passed("V2")
                    v3 += not r.names_to_check
        per_term[term] = {"units": len(units), "promises": t_prom, "v1_pass": round(t_v1 / t_prom, 3) if t_prom else None}
    n_units = sum(len(u) for u in sample.values())
    return {
        "model": model, "calls": calls, "json_valid_first": f"{json_first}/{calls}",
        "units_missing": missing, "promises": promises, "promises_per_unit": round(promises / n_units, 2),
        "v1_pass": round(v1 / promises, 3) if promises else 0.0, "v2_pass": round(v2 / promises, 3) if promises else 0.0,
        "v3_clean": round(v3 / promises, 3) if promises else 0.0,
        "seconds_per_call": round(seconds / calls, 1) if calls else None, "http_retries": http, "per_term": per_term,
    }


def choose(results: list[dict[str, Any]], cfg: Config) -> Optional[str]:
    bulk = cfg.settings.llm.bulk
    ok = [r for r in results if r["v1_pass"] >= bulk.min_v1_pass]
    if not ok:
        return None
    quota = lambda m: bulk.rpd.get(m) or 0  # noqa: E731
    return max(ok, key=lambda r: (r["v1_pass"], quota(r["model"])))["model"]


def write_report(cfg: Config, sample: dict[str, list[Unit]], results: list[dict[str, Any]],
                 winner: Optional[str], stopped: Optional[str]) -> None:
    bulk = cfg.settings.llm.bulk
    lines = [
        "# Backend test (spec 02 §4.8)", "",
        f"Run {dt.date.today().isoformat()}. Sample: " + ", ".join(f"{t} {len(u)}" for t, u in sample.items())
        + f" units (seed {cfg.settings.extract.backend_test.seed}); call shape {cfg.settings.extract.units_per_call}"
        " units per call; prompt `extract_promises`.", "",
        "| Model | Calls | JSON valid 1st | Units missing | Promises | Promises/unit | V1 pass | V2 pass "
        "| V3 clean | s/call | 429/5xx backoffs |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(f"| `{r['model']}` | {r['calls']} | {r['json_valid_first']} | {r['units_missing']} | "
                     f"{r['promises']} | {r['promises_per_unit']} | {r['v1_pass']:.3f} | {r['v2_pass']:.3f} | "
                     f"{r['v3_clean']:.3f} | {r['seconds_per_call']} | {r['http_retries']} |")
    lines += ["", "Per term (V1 pass): " + "; ".join(
        f"`{r['model']}` " + ", ".join(f"{t} {v['v1_pass']} ({v['promises']} promises)" for t, v in r["per_term"].items())
        for r in results), "",
        "V3 clean = share of promises with no capitalised name absent from the unit (Tamil units: transliterated "
        "names are always 'absent', so this is low by design; for English it is a failure).", "",
        f"**Rule:** highest V1 pass rate wins, ties to the larger daily quota; minimum {bulk.min_v1_pass}.", "",
        f"**Choice:** `{winner}`" if winner else ("**No choice: incomplete run.**" if stopped else
                                                  "**No candidate reached the minimum: stop and ask the user "
                                                  "(Kaggle fallback).**"), "",
        "**Free-tier limits** (requests/day per model, `llm.bulk.rpd`): " + ", ".join(
            f"`{m}` {v if v is not None else 'unknown'}" for m, v in bulk.rpd.items()) + f"; rpm setting {bulk.rpm}."]
    if stopped:
        lines += ["", f"**Incomplete:** {stopped}"]
    sample_ids = {t: [u.unit_id for u in us] for t, us in sample.items()}
    lines += ["", "Sample unit IDs (never used as few-shot examples): " + json.dumps(sample_ids)]
    path = cfg.path("backend_test_md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def set_bulk_model(cfg: Config, model: str) -> None:
    """Write the winner into llm.models.bulk in settings.yaml, keeping the file's comments."""
    path = cfg.root / "config" / "settings.yaml"
    text = path.read_text(encoding="utf-8")
    new, n = re.subn(r"(?m)^(    bulk: )\S+(\s*#.*)?$", lambda m: f"{m.group(1)}{model}" + (
        "                # set by `ept extract backend-test` (spec 02 §4.8)"), text, count=1)
    if n != 1:
        raise RuntimeError("llm.models.bulk line not found in settings.yaml")
    path.write_text(new, encoding="utf-8")


def run_backend_test(models: Optional[list[str]] = None) -> dict[str, Any]:
    cfg = get_config()
    candidates = models or cfg.settings.llm.bulk.candidates
    run_id = start_run("extract-backend-test", {"candidates": candidates})
    sample = draw_sample(cfg)
    client = LLMClient(cfg)
    results, stopped = [], None
    try:
        for m in candidates:
            try:
                results.append(evaluate(cfg, client, m, sample))
            except QuotaExhausted as e:
                stopped = f"{m}: {e}"
        complete = not stopped and models is None  # a partial run (--model) never sets the choice
        winner = choose(results, cfg) if complete else None
        write_report(cfg, sample, results, winner, stopped or (None if complete else "partial run (--model)"))
        if winner:
            set_bulk_model(cfg, winner)
    finally:
        finish_run(run_id, {"results": results, "stopped": stopped}, models={"candidates": candidates})
    return {"results": results, "winner": winner, "stopped": stopped}
