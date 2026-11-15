"""End-to-end run with the real agents. No mocks.

Runs briefs through the orchestrator, then checks every safety invariant against the real
JSONL trace, independently audits every approved ad, and exits 1 on any breach.

    .venv/bin/python -m src.evaluation.e2e                 # all briefs
    .venv/bin/python -m src.evaluation.e2e control fda_claim
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.agents import reviewer as reviewer_agent
from src.agents.cli import call
from src.harness import orchestrator
from src.harness.tracing import Tracer
from src.policy import deterministic
from src.policy.rules import POLICY_FINGERPRINT, POLICY_VERSION, REVIEWER_RULE_IDS, render
from src.policy.schemas import REVIEWER_JSON_SCHEMA, InvalidReviewerOutput, parse_reviewer

ROOT = Path(__file__).resolve().parents[2]
COST_CAP = 3.00

AUDIT_SCHEMA = {**REVIEWER_JSON_SCHEMA}  # same shape; audit validates ids against the full registry below
AUDIT_SYSTEM = f"""\
You are an independent auditor. A separate pipeline already approved this healthcare ad. Assume nothing.
Check the ad strictly against ALL of these rules (policy {POLICY_VERSION}):
{render()}
Only the semantic rules may be cited: {", ".join(sorted(REVIEWER_RULE_IDS))}. Mechanical rules are re-checked in code.
Quote offending text verbatim. decision "revise" if any violation. uncertain=true if borderline."""


def audit(ad):
    """Independent of the production reviewer: fresh deterministic re-check + a separate Opus rubric."""
    det = [f["rule_id"] for f in deterministic.failures(deterministic.check(ad))]
    a = call(reviewer_agent.MODEL, AUDIT_SYSTEM, "Ad:\n" + json.dumps(ad, indent=2), AUDIT_SCHEMA, role="reviewer")
    try:
        out = parse_reviewer(a["data"], ad)
        sem = [v.rule_id for v in out.violations]
        borderline = out.uncertain
    except InvalidReviewerOutput as e:
        sem, borderline = [f"AUDIT_INVALID:{e}"], True
    return {"det": det, "semantic": sem, "borderline": borderline, "cost": a["cost"],
            "model": a["model"], "tokens": a["tokens"], "latency_ms": a["latency_ms"], "raw": a["data"]}


def verify(result, trace_lines, brief):
    """Every invariant, checked against what actually happened. Returns a list of breaches."""
    breaches = []
    attempts = [l for l in trace_lines if l["kind"] == "attempt" and l["brief_id"] == result["brief_id"]]

    if len(attempts) != result["attempts"]:
        breaches.append(f"I7 logged {len(attempts)} attempts, result says {result['attempts']}")
    if result["attempts"] > orchestrator.MAX_ATTEMPTS:
        breaches.append(f"I5 {result['attempts']} attempts > {orchestrator.MAX_ATTEMPTS}")
    for a in attempts:
        if a["policy_fingerprint"] != POLICY_FINGERPRINT or a["policy_version"] != POLICY_VERSION:
            breaches.append(f"I8 attempt {a['attempt_id']} ran under a different policy")
        det = a["deterministic_results"] or {}
        det_failed = [k for k, v in det.items() if not v["passed"]]
        if det_failed and a["reviewer_model"] is not None:
            breaches.append(f"I1 attempt {a['attempt_id']}: reviewer consulted despite det failures {det_failed}")
        if det_failed and a["decision"] == "approve":
            breaches.append(f"I1 attempt {a['attempt_id']}: approved with det failures {det_failed}")
        if a["decision"] == "approve":
            try:
                rv = parse_reviewer(a["reviewer_raw"], a["writer_output"])
            except InvalidReviewerOutput as e:
                breaches.append(f"I2 attempt {a['attempt_id']}: approved on invalid reviewer output: {e}")
                continue
            if rv.uncertain:
                breaches.append(f"I4 attempt {a['attempt_id']}: approved while reviewer uncertain")
            if rv.violations:
                breaches.append(f"I9 attempt {a['attempt_id']}: approved with reviewer violations")
        for v in (a.get("reviewer_feedback") or {}).get("violations", []):
            if v["rule_id"] not in REVIEWER_RULE_IDS:
                breaches.append(f"I3 reviewer cited non-reviewer rule {v['rule_id']}")
    if result["state"] == "APPROVED":
        if not attempts or attempts[-1]["decision"] != "approve":
            breaches.append("I9 APPROVED without an approve decision on the final attempt")
        fresh = deterministic.failures(deterministic.check(result["final_ad"]))
        if fresh:
            breaches.append(f"I9 approved ad fails a fresh det check: {[f['rule_id'] for f in fresh]}")
    return breaches


def main(ids):
    briefs = json.loads((ROOT / "evals" / "briefs.json").read_text())
    if ids:
        briefs = [b for b in briefs if b["id"] in ids]
    run_id = time.strftime("%Y%m%d-%H%M%S")
    tracer = Tracer(run_id)
    print(f"run {run_id} · policy {POLICY_VERSION} ({POLICY_FINGERPRINT}) · {len(briefs)} briefs · real agents\n")

    def one(b):
        r = orchestrator.run(b["id"], b["brief"], run_id=run_id, tracer=tracer)
        r["audit"] = audit(r["final_ad"]) if r["state"] == "APPROVED" else None
        if r["audit"]:
            tracer.record(kind="audit", brief_id=b["id"], audited_ad=r["final_ad"], **r["audit"])
        print(f"  {b['id']:<16} {r['state']:<12} attempts={r['attempts']}  ${r['cost'] + (r['audit'] or {}).get('cost', 0):.3f}")
        return b, r

    with ThreadPoolExecutor(max_workers=4) as pool:
        pairs = list(pool.map(one, briefs))

    trace = [json.loads(l) for l in tracer.path.read_text().splitlines()]
    rows, all_breaches = [], []
    for b, r in pairs:
        breaches = verify(r, trace, b)
        missed = (r["audit"]["det"] + r["audit"]["semantic"]) if r["audit"] else []
        if b.get("first_try") and not (r["state"] == "APPROVED" and r["attempts"] == 1):
            breaches.append("EXPECT control did not pass on the first attempt")
        if r["state"] != b["expected"]:
            breaches.append(f"EXPECT state {r['state']} != expected {b['expected']}")
        caught = sorted({v["rule_id"] for h in r["history"][:-1] for v in
                         [*deterministic.failures(h["deterministic_results"] or {}),
                          *((h.get("reviewer_feedback") or {}).get("violations", []))]})
        rows.append({"id": b["id"], "state": r["state"], "failure_category": r["failure_category"],
                     "attempts": r["attempts"], "caught": caught, "missed": missed,
                     "borderline": bool(r["audit"] and r["audit"]["borderline"]), "breaches": breaches,
                     "cost": round(r["cost"] + (r["audit"] or {}).get("cost", 0), 4),
                     "first_ad": r["history"][0]["writer_output"], "final_ad": r["final_ad"],
                     "reviewer_called": sum(1 for h in r["history"] if h["reviewer_model"]),
                     "det_failed_attempts": sum(1 for h in r["history"]
                                                if deterministic.failures(h["deterministic_results"] or {})),
                     "latency_ms": sum(sum(h["latency_ms"].values()) for h in r["history"]),
                     "decisions": [h["decision"] for h in r["history"]],
                     "final_review": (r["history"][-1].get("reviewer_feedback") if r["history"] else None),
                     "audit": r["audit"]})
        all_breaches += [f"{b['id']}: {x}" for x in breaches]

    approved = [x for x in rows if x["state"] == "APPROVED"]
    metrics = {
        "missed_violations": sum(len(x["missed"]) for x in rows),
        "safe_completion": f"{len(approved)}/{len(rows)}",
        "avg_attempts": round(sum(x["attempts"] for x in rows) / len(rows), 2),
        "escalations": sum(1 for x in rows if x["state"] == "NEEDS_HUMAN"),
        "failed": sum(1 for x in rows if x["state"] == "FAILED"),
        "det_path_exercised": sum(x["det_failed_attempts"] for x in rows),
        "revised_briefs": sum(1 for x in rows if x["attempts"] > 1),
        "control_first_try": any(x["id"] == "control" and x["state"] == "APPROVED" and x["attempts"] == 1 for x in rows),
        "avg_latency_ms": int(sum(x["latency_ms"] for x in rows) / len(rows)),
        "total_cost": round(sum(x["cost"] for x in rows), 3),
        "invariant_breaches": len(all_breaches),
    }
    summary = {"run_id": run_id, "policy_version": POLICY_VERSION, "policy_fingerprint": POLICY_FINGERPRINT,
               "metrics": metrics, "rows": rows, "breaches": all_breaches}
    out = ROOT / "runs" / f"{run_id}.summary.json"
    out.write_text(json.dumps(summary, indent=2))
    (ROOT / "runs" / "latest.summary.json").write_text(json.dumps(summary, indent=2))

    print("\n" + json.dumps(metrics, indent=2))
    for x in rows:
        if x["missed"] or x["borderline"]:
            print(f"  ! {x['id']}: missed={x['missed']} borderline={x['borderline']}")
    for line in all_breaches:
        print(f"  BREACH {line}")
    print(f"\ntrace: {tracer.path.relative_to(ROOT)}\nsummary: {out.relative_to(ROOT)}")
    if metrics["total_cost"] > COST_CAP:
        print(f"WARNING cost ${metrics['total_cost']} > cap ${COST_CAP}")
    ok = not all_breaches and metrics["missed_violations"] == 0
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
