"""Reviewer probe set: fixed unsafe (and clean) ads sent straight to the REAL Opus reviewer.

Sonnet almost always writes safe ads, so the end-to-end run rarely tests the reviewer.
These probes do: each ad passes every deterministic check, so only the reviewer can catch it.

    .venv/bin/python -m src.evaluation.probes            # all probes
    .venv/bin/python -m src.evaluation.probes multi clean_1
Exit 0 = every expected violation caught (or escalated as uncertain) and no clean ad rejected.
"""
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.agents import reviewer
from src.harness.context import reviewer_context
from src.harness.retry import InfraError
from src.policy import deterministic
from src.policy.rules import POLICY_FINGERPRINT, POLICY_VERSION
from src.policy.schemas import InvalidReviewerOutput, parse_reviewer

ROOT = Path(__file__).resolve().parents[2]


def prompt_hash():
    return hashlib.sha256(reviewer.SYSTEM.encode()).hexdigest()[:12]


def probe(p):
    try:
        r = reviewer.review(reviewer_context(p["brief"], p["ad"]), POLICY_VERSION)
    except InfraError as e:
        return {**p, "outcome": "infra_error", "error": str(e), "found": [], "cost": 0, "latency_ms": 0}
    try:
        out = parse_reviewer(r["data"], p["ad"])
    except InvalidReviewerOutput as e:
        return {**p, "outcome": "invalid_output", "error": str(e), "found": [], "raw": r["data"],
                "cost": r["cost"], "latency_ms": r["latency_ms"]}
    found = sorted({v.rule_id for v in out.violations})
    expect = set(p["expect"])
    missed = sorted(expect - set(found))
    extra = sorted(set(found) - expect)
    if expect:
        outcome = "caught" if not missed else ("escalated" if out.uncertain else "missed")
    else:
        outcome = "clean_pass" if not found and out.decision == "approve" and not out.uncertain else (
            "clean_escalated" if out.uncertain and not found else "false_positive")
    return {**p, "outcome": outcome, "found": found, "missed": missed, "extra": extra,
            "decision": out.decision, "uncertain": out.uncertain,
            "quotes": [(v.rule_id, v.quote) for v in out.violations],
            "cost": r["cost"], "latency_ms": r["latency_ms"]}


def main(ids):
    probes = json.loads((ROOT / "evals" / "reviewer_probes.json").read_text())
    if ids:
        probes = [p for p in probes if p["id"] in ids]

    # A probe only isolates the reviewer if Python would let the ad through.
    bad = {p["id"]: [f["rule_id"] for f in deterministic.failures(deterministic.check(p["ad"]))] for p in probes}
    bad = {k: v for k, v in bad.items() if v}
    if bad:
        print(f"INVALID PROBES (fail deterministic checks, so they don't isolate the reviewer): {bad}")
        return 2

    run_id = time.strftime("%Y%m%d-%H%M%S")
    print(f"probes {run_id} · {reviewer.MODEL} {reviewer.PROMPT_VERSION} (prompt {prompt_hash()}) · "
          f"policy {POLICY_VERSION} · {len(probes)} probes\n")
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(probe, probes))
    for r in rows:
        mark = "ok " if r["outcome"] in ("caught", "escalated", "clean_pass", "clean_escalated") else "XX "
        print(f"  {mark}{r['id']:<22} {r['outcome']:<15} expect={r['expect'] or '-'} found={r['found'] or '-'}"
              + (f" extra={r['extra']}" if r.get("extra") else ""))

    unsafe = [r for r in rows if r["expect"]]
    clean = [r for r in rows if not r["expect"]]
    expected_total = sum(len(r["expect"]) for r in unsafe)
    hit = sum(len(set(r["expect"]) & set(r["found"])) for r in unsafe)
    flagged = sum(len(r["found"]) for r in rows)
    correct_flags = hit
    m = {
        "unsafe_probes": len(unsafe),
        "caught": sum(r["outcome"] == "caught" for r in unsafe),
        "escalated": sum(r["outcome"] == "escalated" for r in unsafe),
        "missed": sum(r["outcome"] == "missed" for r in unsafe),
        "violation_recall": round(hit / expected_total, 3) if expected_total else None,
        "reviewer_precision": round(correct_flags / flagged, 3) if flagged else None,
        "clean_probes": len(clean),
        "false_positives": sum(r["outcome"] == "false_positive" for r in clean),
        "invalid_outputs": sum(r["outcome"] == "invalid_output" for r in rows),
        "infra_errors": sum(r["outcome"] == "infra_error" for r in rows),
        "total_cost": round(sum(r["cost"] for r in rows), 3),
        "avg_latency_ms": int(sum(r["latency_ms"] for r in rows) / len(rows)),
    }
    summary = {"run_id": run_id, "reviewer_model": reviewer.MODEL, "reviewer_prompt_version": reviewer.PROMPT_VERSION,
               "reviewer_prompt_hash": prompt_hash(), "policy_version": POLICY_VERSION,
               "policy_fingerprint": POLICY_FINGERPRINT, "metrics": m, "rows": rows}
    (ROOT / "runs").mkdir(exist_ok=True)
    out = ROOT / "runs" / f"{run_id}.probes.json"
    out.write_text(json.dumps(summary, indent=2))
    (ROOT / "runs" / "latest.probes.json").write_text(json.dumps(summary, indent=2))
    print("\n" + json.dumps(m, indent=2) + f"\n\nsummary: {out.relative_to(ROOT)}")
    ok = m["missed"] == 0 and m["false_positives"] == 0 and m["invalid_outputs"] == 0 and m["infra_errors"] == 0
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
