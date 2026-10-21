"""`ept judge probe` (spec 05 §4.6, D-092): how often the bulk model answers from memory.

`judge.probe.n` full-term tasks (half AIADMK-2016, half DMK-2021) on self indicators, promises drawn by
sha256(`judge.probe.seed` + promise_id), gold promises excluded. Each task has no extracts ("No extracts were
found for this commitment."); same prompt, `probe.tasks_per_call` per call, own run (kind `probe`). Recorded:
each task's first answer before checks, and the share claiming a status that needs evidence (anything but
`unverifiable`: with no extract on topic, even `not_started` is unsupported, spec 05 §4.4 item 5). Reported,
never used as a verdict.
"""

from __future__ import annotations

import hashlib
from typing import Any

from ept import db
from ept.config import get_config
from ept.judge import directional as dirmod
from ept.judge.bulk import Caller, calls_path, judge_model
from ept.judge.checks import Limits
from ept.judge.prompt import PROMPT
from ept.judge.store import fp_hash, start_or_resume, stored_keys, update_meta, write_indicator_verdicts
from ept.judge.tasks import Context, Key, Task, batches, gold_promise_ids, judging_key
from ept.llm import LLMClient, QuotaExhausted, load_prompt
from ept.runs import finish_run
from ept.schema import IndicatorVerdict

PROBE_TERMS = ("AIADMK-2016", "DMK-2021")
EVIDENCE_FREE = "unverifiable"


def draw(ctx: Context, cfg, gold: set[str]) -> list[Key]:
    p = cfg.settings.judge.probe
    per = p.n // len(PROBE_TERMS)
    flags = dirmod.load_all(cfg, list(PROBE_TERMS))
    keys = []
    for term in PROBE_TERMS:
        full = next(c for c in ctx.cutoffs(term) if c.cutoff_date is None)
        cands = [pid for pid, r in ctx.promises.items() if r["term_id"] == term and pid not in gold
                 and ctx.indicators.get(f"{pid}-I1", {}).get("is_self")]
        cands.sort(key=lambda pid: hashlib.sha256((p.seed + pid).encode()).hexdigest())
        for pid in cands[:per]:
            iid = f"{pid}-I1"
            k = Key(judging_key(iid, [], flags.get(pid, False), "probe:" + load_prompt(PROMPT, cfg).version),
                    term, pid, iid, (), flags.get(pid, False))
            k.tasks.append(Task(term, pid, iid, full, ()))
            keys.append(k)
    return keys


def run_probe(force: bool = False) -> dict[str, Any]:
    cfg = get_config()
    conn = db.connect()
    db.init_schema(conn)
    ctx = Context(conn, cfg)
    keys = draw(ctx, cfg, gold_promise_ids(cfg))
    version = load_prompt(PROMPT, cfg).version
    fp = fp_hash({"keys": [k.key for k in keys], "model": judge_model(cfg), "version": version})
    run_id, resumed = start_or_resume(cfg, "probe", fp, force, {"force": force})
    log = calls_path(cfg, run_id)
    log.parent.mkdir(parents=True, exist_ok=True)
    client = LLMClient(cfg)
    call = Caller(client, ctx, run_id, log, Limits.from_config(cfg), call_kind="probe")
    stored = stored_keys(conn, run_id)
    model = judge_model(cfg)
    stopped = None
    try:
        for b in batches([k for k in keys if k.key not in stored], cfg.settings.judge.probe.tasks_per_call):
            res = call(b, "first", with_extracts=False)
            rows = []
            for k in b:
                ans, chk, fails = res[k.key]
                status = ans.status if ans else "unverifiable"
                rows.append(IndicatorVerdict(
                    indicator_id=k.indicator_id, run_id=run_id, cutoff_date=None, judging_key=k.key, status=status,
                    realisation_date=None, date_precision=None, date_chunk_id=None, cited_chunk_ids=[], quotes={},
                    rationale=" ".join(((ans.rationale if ans else "") or "").split()[:80]),
                    confidence=min(max(ans.confidence, 0.0), 1.0) if ans else 0.0, needs_review=True,
                    review_reasons=["probe"] + ([f"first_answer_date:{ans.realisation_date}"]
                                                if ans and ans.realisation_date else [])
                    + sorted({f.split(':', 1)[0] for f in fails}),
                    judge_source="bulk", judge_model=model, prompt_version=version))
            write_indicator_verdicts(conn, rows)
    except QuotaExhausted as e:
        stopped = str(e)
    rows = [r for r in conn.execute("SELECT status FROM indicator_verdicts WHERE run_id = ?", (run_id,))]
    n = len(rows)
    claims = sum(r["status"] != EVIDENCE_FREE for r in rows)
    realised = sum(r["status"] in ("fulfilled", "partial", "diluted") for r in rows)
    stats = {"run_id": run_id, "resumed": resumed, "tasks": n, "planned": len(keys), "evidence_claims": claims,
             "evidence_share": round(claims / n, 4) if n else None, "realised_claims": realised,
             "stop_for_user": bool(n and claims / n > cfg.settings.judge.probe_max_share), "stopped": stopped,
             "llm_calls": client.calls}
    finish_run(run_id, counts=stats, models={"bulk": model}, status="stopped" if stopped else "done")
    update_meta(cfg, run_id, kind="probe", fingerprint=fp, complete=n == len(keys))
    conn.close()
    return stats
