"""Versioned policy registry. Agents read this; nothing at runtime writes to it."""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

POLICY_VERSION = "2026-11-15.1"
# sha256 of registry + deterministic patterns; tests/test_policy.py pins it. Change policy => bump both.
POLICY_FINGERPRINT = "9335ec37be3c3d04"

HEADLINE_MAX = 40
BODY_MAX = 125
CTA_MAX = 20
ALLOWED_CTAS = frozenset({"Start your visit", "See if you qualify", "Learn more"})


@dataclass(frozen=True)
class Rule:
    id: str
    owner: Literal["deterministic", "reviewer"]
    severity: Literal["high", "medium"]
    text: str


_RULES = (
    Rule("FDA_CLAIM", "deterministic", "high", 'Never claim FDA approval (our medications are compounded).'),
    Rule("GUARANTEED_OUTCOME", "deterministic", "high", "No guarantees of results."),
    Rule("WEIGHT_PROMISE", "deterministic", "high", "No promised pound/kg numbers or quantified weight-loss outcomes."),
    Rule("RESULTS_DISCLOSURE", "deterministic", "high", 'Body must include "Results vary."'),
    Rule("SAFETY_DISCLOSURE", "deterministic", "high", 'Reference important safety information (e.g. "See safety info.").'),
    Rule("HEADLINE_LENGTH", "deterministic", "medium", f"Headline <= {HEADLINE_MAX} characters."),
    Rule("BODY_LENGTH", "deterministic", "medium", f"Body <= {BODY_MAX} characters."),
    Rule("CTA_LENGTH", "deterministic", "medium", f"CTA exactly one of: {', '.join(sorted(ALLOWED_CTAS))}."),
    Rule("OUTPUT_SCHEMA", "deterministic", "high", "headline, body and cta are present non-empty strings."),
    Rule("IMPLIED_OUTCOME", "reviewer", "high", 'No implied guaranteed or specific outcomes, even without numbers ("melt the fat away", "dream body").'),
    Rule("PROVIDER_RESPONSIBILITY", "reviewer", "high", "Make clear a licensed provider decides whether treatment is appropriate; never imply automatic prescription."),
    Rule("BEFORE_AFTER", "reviewer", "high", 'No before/after framing or transformation timelines ("you in 90 days").'),
    Rule("MINORS", "reviewer", "high", "Nothing that targets or implies minors (teens, students, school events)."),
    Rule("BODY_SHAMING", "reviewer", "high", "No body-shaming or appearance-shaming language."),
)

REGISTRY = MappingProxyType({r.id: r for r in _RULES})
REVIEWER_RULE_IDS = frozenset(r.id for r in _RULES if r.owner == "reviewer")


def render(owner=None):
    return "\n".join(f"{r.id}: {r.text}" for r in _RULES if owner in (None, r.owner))
