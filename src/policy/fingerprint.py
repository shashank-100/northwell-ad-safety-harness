"""Hash of everything that defines policy. Any edit to rules or patterns changes it."""
import hashlib
import json

from src.policy import deterministic, rules


def compute():
    payload = {
        "rules": [[r.id, r.owner, r.severity, r.text] for r in rules.REGISTRY.values()],
        "limits": [rules.HEADLINE_MAX, rules.BODY_MAX, rules.CTA_MAX, sorted(rules.ALLOWED_CTAS)],
        "patterns": {k: list(v) for k, v in deterministic.PATTERNS.items()},
        "required": dict(deterministic.REQUIRED),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
