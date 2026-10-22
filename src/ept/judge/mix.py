"""`ept judge run-b-reverse` (D-097): the bulk model judges tier B from the latest landmark backwards, while
Claude subagents judge tier B (strong level `tier_b`) from the earliest landmark forwards.

Same prompt, checks, retries and rows as `ept judge run` (it reuses `ept.judge.bulk`), written into the same
bulk run (same fingerprint), only with the (term, judging cutoff) groups in reverse time order. `--stop-at`
(a cutoff date) ends the pass before that group, where Claude has already arrived. Final verdicts take the strong
verdict where a promise × cutoff is complete in the strong run, else the bulk one (spec 05 §4.10).
"""

from __future__ import annotations

import time
from typing import Any, Optional

from ept import db
from ept.config import get_config
from ept.judge import directional as dirmod
from ept.judge.bulk import (Caller, StopForUser, calls_path, fingerprint, judge_group, judge_model, rows_for,
                            failure_rows, unresolved_keys, write_failures, _record_tier)
from ept.judge.checks import Limits
from ept.judge.prompt import PROMPT
from ept.judge.store import read_meta, start_or_resume, stored_keys, write_indicator_verdicts
from ept.judge.tasks import Context, build_keys, groups, load_retrievals
from ept.llm import LLMClient, QuotaExhausted, load_prompt
from ept.retrieve.run import latest_run as latest_retrieval
from ept.runs import progress


def run_reverse(tier: str = "B", stop_at: Optional[str] = None) -> dict[str, Any]:
    cfg = get_config()
    j = cfg.settings.judge
    conn = db.connect()
    ctx = Context(conn, cfg)
    rmeta = latest_retrieval(cfg, complete_only=True)
    terms = [t.term_id for t in cfg.settings.terms]
    version = load_prompt(PROMPT, cfg).version
    keys = build_keys(ctx, load_retrievals(conn, rmeta["run_id"]), dirmod.load_all(cfg, terms), version, terms)
    fp = fingerprint(cfg, rmeta["run_id"], version, terms)
    run_id, resumed = start_or_resume(cfg, "bulk", fp, False, {"tier": tier, "reverse": True},
                                      extra={"retrieval_run": rmeta["run_id"], "tiers": {}})
    log = calls_path(cfg, run_id)
    client = LLMClient(cfg)
    call = Caller(client, ctx, run_id, log, Limits.from_config(cfg))
    model = judge_model(cfg)
    tier_keys = [k for k in keys if tier in k.tiers]
    stored = stored_keys(conn, run_id)
    todo = [k for k in tier_keys if k.key not in stored]
    unresolved = len(unresolved_keys(conn, run_id) & {k.key for k in tier_keys})
    stats: dict[str, Any] = {"run_id": run_id, "resumed": resumed, "keys_written": 0, "unresolved": unresolved,
                             "stopped": None, "stop_for_user": None, "groups": []}
    fails: list[dict[str, Any]] = []
    try:
        for grp in reversed(groups(todo, terms)):
            cut = grp[0].judging
            if stop_at and cut.cutoff_date and cut.cutoff_date.isoformat() <= stop_at:
                break
            outcomes = judge_group(call, grp, j.bulk.tasks_per_call, j.bulk.retry_tasks_per_call,
                                   lambda b: progress(f"judge run-b-reverse: {b[0].term_id} {b[0].judging.label}: "
                                                      f"{len(b)} keys, {client.calls} calls"))
            write_indicator_verdicts(conn, [r for o in outcomes for r in rows_for(o, run_id, model, version, cfg)])
            fails += [r for o in outcomes for r in failure_rows(o, run_id)]
            unresolved += sum(o.checked is None for o in outcomes)
            stats["keys_written"] += len(grp)
            stats["groups"].append(f"{grp[0].term_id}@{cut.key}")
            if unresolved > j.max_unresolved_share * len(tier_keys):
                raise StopForUser(f"tier {tier}: {unresolved} unresolved keys > {j.max_unresolved_share:.0%}")
        _record_tier(cfg, conn, run_id, tier, keys, unresolved)
    except QuotaExhausted as e:
        stats["stopped"] = str(e)
    except StopForUser as e:
        stats["stop_for_user"] = str(e)
    finally:
        write_failures(cfg, run_id, fails)
        conn.close()
    stats.update(unresolved=unresolved, llm_calls=client.calls, at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                 tiers=read_meta(cfg, run_id).get("tiers", {}))
    return stats
