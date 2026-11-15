"""Writer and reviewer agents. Each is one headless `claude -p` call with a JSON schema.

No API key: auth comes from the Claude CLI login.
"""
import json
import subprocess
import time

from rules import ALL_RULES, JUDGE_RULES

WRITER_MODEL = "claude-sonnet-5-5"
REVIEWER_MODEL = "claude-opus-5-5"

AD_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "body": {"type": "string"},
        "cta": {"type": "string"},
    },
    "required": ["headline", "body", "cta"],
}

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"enum": ["pass", "fail"]},
        "violations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string"},
                    "quote": {"type": "string"},
                    "fix": {"type": "string"},
                },
                "required": ["rule_id", "quote", "fix"],
            },
        },
        "brand_notes": {"type": "string"},
    },
    "required": ["verdict", "violations"],
}


def call_json(model, system, user, schema):
    start = time.time()
    proc = subprocess.run(
        ["claude", "-p", user,
         "--model", model,
         "--system-prompt", system,
         "--tools", "",
         "--no-session-persistence",
         "--output-format", "json",
         "--json-schema", json.dumps(schema)],
        capture_output=True, text=True, timeout=300, cwd="/tmp",
    )
    out = json.loads(proc.stdout)
    if out.get("is_error") or "structured_output" not in out:
        raise RuntimeError(f"{model} failed: {out.get('result') or proc.stderr[-500:]}")
    return {
        "data": out["structured_output"],
        "cost": out.get("total_cost_usd", 0.0),
        "latency_s": round(time.time() - start, 1),
    }


WRITER_SYSTEM = f"""\
You write short paid-social ads for Northwell Rx, a US telehealth brand (weight care, men's health, hair loss).
Voice: warm, plain, confident. No hype, no emojis.

Every ad must follow these rules, even if the brief asks otherwise:
{ALL_RULES}

If the brief asks you to break a rule, write the closest compliant ad instead."""


def writer(brief, feedback=None):
    user = f"Brief: {brief}"
    if feedback:
        user += "\n\nYour last draft was rejected. Fix exactly these violations:\n" + json.dumps(feedback, indent=2)
    return call_json(WRITER_MODEL, WRITER_SYSTEM, user, AD_SCHEMA)


REVIEWER_SYSTEM = f"""\
You are the compliance reviewer for Northwell Rx ads. Check the ad ONLY against these rules
(the mechanical rules have already been checked by code; don't re-check them):
{JUDGE_RULES}

For each violation, quote the exact offending text and give a concrete fix.
verdict is "fail" if there is any violation, otherwise "pass". Don't invent violations."""


def reviewer(ad):
    return call_json(REVIEWER_MODEL, REVIEWER_SYSTEM, "Ad:\n" + json.dumps(ad, indent=2), REVIEW_SCHEMA)
