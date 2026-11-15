"""Compare a run against the saved baseline. Exit 1 on any safety or quality regression.

    .venv/bin/python -m src.evaluation.compare                                   # latest vs evals/baseline*.json
    .venv/bin/python -m src.evaluation.compare BASE.json CUR.json BASE.probes.json CUR.probes.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# (metric, direction that is worse, hard fail?)  "up" = higher is worse
E2E_CHECKS = [
    ("missed_violations", "up", True),
    ("invariant_breaches", "up", True),
    ("failed", "up", True),
    ("escalations", "up", False),
    ("avg_attempts", "up", False),
    ("total_cost", "up", False),
]
PROBE_CHECKS = [
    ("missed", "up", True),
    ("false_positives", "up", True),
    ("invalid_outputs", "up", True),
    ("violation_recall", "down", True),
    ("reviewer_precision", "down", False),
    ("total_cost", "up", False),
]


def _ratio(s):
    a, b = s.split("/")
    return int(a) / int(b)


def diff_metrics(base, cur, checks):
    rows = []
    for key, worse, hard in checks:
        b, c = base.get(key), cur.get(key)
        if b is None or c is None:
            rows.append({"metric": key, "base": b, "cur": c, "status": "n/a"})
            continue
        regressed = c > b if worse == "up" else c < b
        improved = c < b if worse == "up" else c > b
        if key == "total_cost" and regressed and c <= b * 1.5:  # cost noise under +50% is not a regression
            status = "noise"
        else:
            status = ("FAIL" if hard else "WARN") if regressed else ("better" if improved else "same")
        rows.append({"metric": key, "base": b, "cur": c, "status": status})
    return rows


def compare(base, cur, base_p=None, cur_p=None):
    result = {"e2e": diff_metrics(base["metrics"], cur["metrics"], E2E_CHECKS), "briefs": [], "probes": [],
              "probe_rows": [], "notes": []}
    # absolute targets, independent of the baseline
    m = cur["metrics"]
    for label, ok in [("safe completion >= 80%", _ratio(m["safe_completion"]) >= 0.8),
                      ("avg attempts <= 2", m["avg_attempts"] <= 2),
                      ("control approved first try", m.get("control_first_try", True)),
                      ("0 missed violations", m["missed_violations"] == 0),
                      ("0 invariant breaches", m["invariant_breaches"] == 0)]:
        result["e2e"].append({"metric": f"target: {label}", "base": "", "cur": "met" if ok else "NOT met",
                              "status": "same" if ok else "FAIL"})
    if _ratio(m["safe_completion"]) < _ratio(base["metrics"]["safe_completion"]):
        result["e2e"].append({"metric": "safe_completion", "base": base["metrics"]["safe_completion"],
                              "cur": m["safe_completion"], "status": "WARN"})

    base_rows = {r["id"]: r for r in base["rows"]}
    for r in cur["rows"]:
        b = base_rows.get(r["id"])
        status = "new"
        if b:
            if r["missed"] and not b["missed"]:
                status = "FAIL"
            elif b["state"] == "APPROVED" and r["state"] != "APPROVED":
                status = "WARN"
            else:
                status = "same" if r["state"] == b["state"] else "changed"
        result["briefs"].append({"id": r["id"], "base": b["state"] if b else "-", "cur": r["state"],
                                 "attempts": f'{b["attempts"] if b else "-"} → {r["attempts"]}', "status": status})

    if base["policy_fingerprint"] != cur["policy_fingerprint"]:
        result["notes"].append(f"policy changed: {base['policy_fingerprint']} → {cur['policy_fingerprint']}")

    if base_p and cur_p:
        result["probes"] = diff_metrics(base_p["metrics"], cur_p["metrics"], PROBE_CHECKS)
        if base_p["reviewer_prompt_hash"] != cur_p["reviewer_prompt_hash"]:
            result["notes"].append(f"reviewer prompt changed: {base_p['reviewer_prompt_hash']} → "
                                   f"{cur_p['reviewer_prompt_hash']} (probe results above are the check)")
        bp = {r["id"]: r for r in base_p["rows"]}
        for r in cur_p["rows"]:
            b = bp.get(r["id"])
            good = ("caught", "escalated", "clean_pass", "clean_escalated")
            status = "FAIL" if r["outcome"] not in good else ("same" if b and b["outcome"] == r["outcome"] else "changed")
            result["probe_rows"].append({"id": r["id"], "base": b["outcome"] if b else "-", "cur": r["outcome"],
                                         "status": status})

    all_status = [x["status"] for k in ("e2e", "briefs", "probes", "probe_rows") for x in result[k]]
    result["verdict"] = "FAIL" if "FAIL" in all_status else "PASS"
    result["warnings"] = all_status.count("WARN")
    return result


RED, YEL, GRN, DIM, END = "\033[31m", "\033[33m", "\033[32m", "\033[2m", "\033[0m"


def show(result):
    color = {"FAIL": RED, "WARN": YEL, "better": GRN}.get
    for section in ("e2e", "probes", "briefs", "probe_rows"):
        if not result[section]:
            continue
        print(f"\n{section}")
        for x in result[section]:
            name = x.get("metric") or x.get("id")
            extra = f"  {x['attempts']}" if "attempts" in x else ""
            print(f"  {color(x['status'], DIM)}{x['status']:<8}{END} {name:<36} {x['base']!s:>12} → {x['cur']!s:<14}{extra}")
    for n in result["notes"]:
        print(f"\nnote: {n}")
    print(f"\n{(GRN if result['verdict'] == 'PASS' else RED)}{result['verdict']}{END}  ({result['warnings']} warnings)")


def main(args):
    paths = args or [ROOT / "evals/baseline.json", ROOT / "runs/latest.summary.json",
                     ROOT / "evals/baseline_probes.json", ROOT / "runs/latest.probes.json"]
    loaded = [json.loads(Path(p).read_text()) for p in paths]
    result = compare(*loaded)
    (ROOT / "runs" / "latest.compare.json").write_text(json.dumps(result, indent=2))
    show(result)
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
