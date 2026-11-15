"""Export prompts, policy, schemas and renderer CSS from the Python source so the Worker can't drift from it.

    ../.venv/bin/python build_shared.py      (run from app/worker)
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agents import creative_spec, reviewer, writer  # noqa: E402
from src.evaluation import creative  # noqa: E402
from src.policy import deterministic, rules  # noqa: E402
from src.policy.fingerprint import compute  # noqa: E402
from src.policy.schemas import REVIEWER_JSON_SCHEMA, writer_json_schema  # noqa: E402

assert compute() == rules.POLICY_FINGERPRINT, "policy fingerprint mismatch"
shared = {
    "policy_version": rules.POLICY_VERSION,
    "policy_fingerprint": rules.POLICY_FINGERPRINT,
    "writer_system": writer.SYSTEM.replace("{policy_version}", rules.POLICY_VERSION)
                     + "\n\nWrite plain text only: no markdown, no asterisks, no emojis.",
    "reviewer_system": reviewer.SYSTEM.replace("{policy_version}", rules.POLICY_VERSION),
    "writer_prompt_version": writer.PROMPT_VERSION + "+workers-ai",
    "reviewer_prompt_version": reviewer.PROMPT_VERSION + "+workers-ai",
    "writer_schema": writer_json_schema(),
    "reviewer_schema": REVIEWER_JSON_SCHEMA,
    "patterns": {k: list(v) for k, v in deterministic.PATTERNS.items()},
    "required": dict(deterministic.REQUIRED),
    "number_words": deterministic.NUMBER_WORDS,
    "limits": {"headline": rules.HEADLINE_MAX, "body": rules.BODY_MAX, "cta": rules.CTA_MAX},
    "allowed_ctas": sorted(rules.ALLOWED_CTAS),
    "reviewer_rule_ids": sorted(rules.REVIEWER_RULE_IDS),
    "palettes": creative_spec.PALETTES,
    "fonts": creative.FONTS,
    "css": creative.CSS,
}
(Path(__file__).parent / "src" / "shared.json").write_text(json.dumps(shared, indent=1))
for f in ("report.html", "creative_before_after.html"):
    shutil.copy(ROOT / "reports" / f, Path(__file__).parent / "public" / ("index.html" if f == "report.html" else f))
print("wrote src/shared.json and public/ ·", rules.POLICY_VERSION, rules.POLICY_FINGERPRINT)
