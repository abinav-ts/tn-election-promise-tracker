"""Gold-set draw (spec 06 §G3) — standalone prototype, stdlib + PyYAML only.

Claude Code ports this to `ept evaluate gold draw`; a test must reproduce
`data/gold/gold_sample.csv` byte for byte from the frozen snapshots.

Order rule: any prefix of the core block (positions 1..70) is a stratified
sample (equal per term; specificity share fixed with a vague floor; sectors
proportional within specificity; at most one promise per manifesto unit).
Randomness comes only from sha256(seed + ":" + id), so the order is the same
on every machine and Python version.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SEED = "ept-gold-2026-10-20"           # fixed in spec 06 §G3; never re-rolled to taste
CORE_TERMS = ["AIADMK-2016", "DMK-2021"]  # interleaved A, D, A, D, ...
CORE_PER_TERM = 35                     # 70 core positions
FLOOR = 40                             # minimum labelled prefix (20 + 20)
TAIL_TERM = "TVK-2026"
TAIL_N = 8
TAIL_AFTER = 40                        # TVK block occupies positions 41..48
VAGUE_FLOOR = 0.15                     # vague share per term = max(natural, floor)
ALGO_VERSION = "gold-draw-v1"


def h(key: str) -> str:
    return hashlib.sha256(f"{SEED}:{key}".encode()).hexdigest()


def load_term(term: str) -> list[dict]:
    prom = {json.loads(l)["promise_id"]: json.loads(l)
            for l in open(ROOT / f"data/frozen/promises_{term}.jsonl", encoding="utf-8")}
    rows = []
    for l in open(ROOT / f"data/frozen/classification_{term}.jsonl", encoding="utf-8"):
        c = json.loads(l)
        p = prom[c["promise_id"]]
        rows.append({"promise_id": p["promise_id"], "term_id": term, "parent_group": p["parent_group"],
                     "sector": c["sector"], "specificity": c["specificity"], "headline": bool(c["headline"])})
    return rows


def ordered_draw(rows: list[dict], k: int) -> list[dict]:
    """Two-level largest-deficit sequence: specificity first, then sector within it."""
    n_spec = Counter(r["specificity"] for r in rows)
    s_vague = max(n_spec["vague"] / len(rows), VAGUE_FLOOR)
    share = {"vague": s_vague, "specific": 1 - s_vague}
    pools: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        pools[(r["specificity"], r["sector"])].append(r)
    for key in pools:
        pools[key].sort(key=lambda r: h(r["promise_id"]))
    sec_share = {sp: {sec: len(v) / n_spec[sp] for (s2, sec), v in pools.items() if s2 == sp} for sp in share}
    used_units: set[str] = set()
    got_spec: Counter = Counter()
    got_sec: dict[str, Counter] = defaultdict(Counter)
    out = []

    def next_in(key):
        while pools[key]:
            r = pools[key].pop(0)
            if r["parent_group"] not in used_units:
                return r
        return None

    while len(out) < k:
        n = len(out) + 1
        picked = None
        for sp in sorted(share, key=lambda s: (-(share[s] * n - got_spec[s]), h("spec:" + s))):
            m = got_spec[sp] + 1
            secs = sorted((sec for sec in sec_share[sp] if pools[(sp, sec)]),
                          key=lambda sec: (-(sec_share[sp][sec] * m - got_sec[sp][sec]), h("sec:" + sec)))
            for sec in secs:
                r = next_in((sp, sec))
                if r:
                    picked = r
                    break
            if picked:
                break
        if picked is None:
            break
        used_units.add(picked["parent_group"])
        got_spec[picked["specificity"]] += 1
        got_sec[picked["specificity"]][picked["sector"]] += 1
        out.append(picked)
    return out


def main() -> None:
    draws = {t: ordered_draw(load_term(t), CORE_PER_TERM) for t in CORE_TERMS}
    tail = ordered_draw(load_term(TAIL_TERM), TAIL_N)
    core = [draws[t][i] for i in range(CORE_PER_TERM) for t in CORE_TERMS]
    order = core[:TAIL_AFTER] + tail + core[TAIL_AFTER:]
    out_path = ROOT / "data/gold/gold_sample.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["order", "promise_id", "term_id", "block", "specificity", "sector", "headline", "parent_group"])
        for i, r in enumerate(order, 1):
            block = "tvk_tail" if r["term_id"] == TAIL_TERM else ("core_floor" if i <= FLOOR else "core_extra")
            w.writerow([i, r["promise_id"], r["term_id"], block, r["specificity"], r["sector"],
                        int(r["headline"]), r["parent_group"]])
    meta = {"algo": ALGO_VERSION, "seed": SEED, "core_terms": CORE_TERMS, "core_per_term": CORE_PER_TERM,
            "floor": FLOOR, "tail_term": TAIL_TERM, "tail_n": TAIL_N, "tail_after": TAIL_AFTER,
            "vague_floor": VAGUE_FLOOR, "n": len(order),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "snapshot_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for t in CORE_TERMS + [TAIL_TERM]
                                for p in [ROOT / f"data/frozen/promises_{t}.jsonl",
                                          ROOT / f"data/frozen/classification_{t}.jsonl"]}}
    (ROOT / "data/gold/gold_sample_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    # summary
    for label, rows in [("floor 1-40 (core)", [r for r in order[:FLOOR]]), ("all", order)]:
        print(label, Counter(r["term_id"] for r in rows), Counter((r["term_id"], r["specificity"]) for r in rows),
              "headline", sum(r["headline"] for r in rows))
    print("sectors in floor:", Counter((r["term_id"][:3], r["sector"]) for r in order[:FLOOR]).most_common())


if __name__ == "__main__":
    sys.exit(main())
