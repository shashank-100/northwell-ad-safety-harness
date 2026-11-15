"""write -> deterministic checks -> LLM review -> retry with structured feedback (max 3 retries)."""
import json
import sys
from pathlib import Path

import rules
from agents import reviewer, writer

TRACES = Path(__file__).parent / "results" / "traces"


def run(brief_id, brief, max_retries=3):
    TRACES.mkdir(parents=True, exist_ok=True)
    trace = TRACES / f"{brief_id}.jsonl"
    trace.write_text("")
    feedback, cost, caught = None, 0.0, []

    for attempt in range(1, max_retries + 2):
        w = writer(brief, feedback)
        ad, cost = w["data"], cost + w["cost"]
        step = {"attempt": attempt, "ad": ad, "writer_cost": w["cost"]}

        violations = rules.check(ad)
        source = "deterministic"
        if not violations:  # only pay for Opus once the free checks pass
            r = reviewer(ad)
            cost += r["cost"]
            step["reviewer_cost"] = r["cost"]
            violations = r["data"]["violations"] if r["data"]["verdict"] == "fail" else []
            source = "judge"

        step.update(source=source, violations=violations)
        with trace.open("a") as f:
            f.write(json.dumps(step) + "\n")

        if not violations:
            return {"brief_id": brief_id, "status": "approved", "attempts": attempt,
                    "final_ad": ad, "caught": caught, "cost": round(cost, 4)}
        caught += [v["rule_id"] for v in violations]
        feedback = violations

    return {"brief_id": brief_id, "status": "needs_human", "attempts": attempt,
            "final_ad": ad, "caught": caught, "cost": round(cost, 4)}


if __name__ == "__main__":
    briefs = json.loads((Path(__file__).parent / "briefs.json").read_text())
    b = next(b for b in briefs if b["id"] == (sys.argv[1] if len(sys.argv) > 1 else "b01"))
    print(json.dumps(run(b["id"], b["brief"]), indent=2))
