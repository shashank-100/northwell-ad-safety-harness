# Northwell Rx — Agentic Ad Safety Harness

A two-agent pipeline that writes healthcare ad copy and refuses to approve anything unsafe.

**Live report:** https://northwell-ad-safety.shashank-telkhade.workers.dev/
Northwell Rx is a fictional telehealth brand.

```
brief (untrusted) → Writer (Sonnet 5.5) → deterministic policy engine (Python) → Reviewer (Opus 5.5) → approval gate
                         ↑                         │ fail                              │ revise
                         └──── structured violations, max 3 attempts ─────────────────┘ → NEEDS_HUMAN
```

- **Deterministic first.** FDA claims, guarantees, weight numbers, required disclosures, lengths and schema are checked in
  code. An LLM can never override them.
- **The orchestrator owns approval.** It's an explicit state machine. Invalid reviewer JSON, unknown rule ids, quotes not
  found in the ad, or reviewer uncertainty all fail closed to `NEEDS_HUMAN`.
- **Untrusted input stays data.** Briefs and model output are escaped before being wrapped in delimiter tags.
- **Verified by running the real agents.** No unit tests and no mocks: every invariant is checked against the real JSONL
  trace, an independent Opus audit re-checks every approved ad, and a fixed probe set measures the reviewer on its own.

## Run it
Requires the [Claude Code CLI](https://claude.com/claude-code) logged in, and Python 3.12+.
```bash
python3 -m venv .venv && .venv/bin/pip install pydantic
.venv/bin/python -m src.evaluation.e2e        # 12 briefs end to end, invariant checks, audit
.venv/bin/python -m src.evaluation.probes     # 16 fixed ads straight to the reviewer
.venv/bin/python -m src.evaluation.compare    # regression vs baseline, exit 1 on regression
.venv/bin/python -m src.evaluation.report     # reports/report.html
```

## Latest results (15 Nov 2026)
| | |
|---|---|
| End to end | 12/12 safe completions, 0 missed violations, 0 invariant breaches, 1.08 avg attempts, $0.50 |
| Reviewer probes | 13/13 unsafe ads caught, 0 clean ads rejected, precision 71% |
| Regression vs baseline | PASS |

Prototype acceptance targets, not a claim of regulatory compliance. See `AGENTS.md` for the full verification
workflow and `CLAUDE.md` for the engineering invariants.
