"""Strict structured-output contracts. Anything that fails validation cannot be approved."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from src.policy.rules import REGISTRY, REVIEWER_RULE_IDS


class Ad(BaseModel):
    model_config = ConfigDict(extra="forbid")
    headline: str
    body: str
    cta: str


class Violation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_id: str
    severity: Literal["high", "medium"] = "high"
    quote: str = ""
    explanation: str = ""
    suggested_fix: str = ""

    @field_validator("rule_id")
    @classmethod
    def known_rule(cls, v):
        if v not in REGISTRY:  # invariant 3: unknown policy ids fail closed
            raise ValueError(f"unknown rule_id {v!r}")
        return v


class ReviewerViolation(Violation):
    @field_validator("rule_id")
    @classmethod
    def reviewer_owned(cls, v):
        # The reviewer may only cite semantic rules; mechanical rules belong to Python.
        if v not in REVIEWER_RULE_IDS:
            raise ValueError(f"reviewer cannot cite {v!r}; allowed: {sorted(REVIEWER_RULE_IDS)}")
        return v


class ReviewerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "revise"]
    violations: list[ReviewerViolation]
    uncertain: bool


class InvalidReviewerOutput(ValueError):
    pass


def parse_reviewer(raw, ad):
    """Validate reviewer output against the schema AND the ad it judged. Raises InvalidReviewerOutput."""
    try:
        out = ReviewerOutput.model_validate(raw)
    except ValidationError as e:
        raise InvalidReviewerOutput(str(e)[:300]) from e
    ad_text = f"{ad['headline']}\n{ad['body']}\n{ad['cta']}"
    for v in out.violations:
        if not v.quote or v.quote not in ad_text:
            raise InvalidReviewerOutput(f"{v.rule_id} quote not found verbatim in ad: {v.quote!r}")
    if out.decision == "approve" and out.violations:
        raise InvalidReviewerOutput("decision 'approve' with violations listed")
    if out.decision == "revise" and not out.violations:
        raise InvalidReviewerOutput("decision 'revise' with no violations")
    return out


AD_JSON_SCHEMA = {
    "type": "object",
    "properties": {"headline": {"type": "string"}, "body": {"type": "string"}, "cta": {"type": "string"}},
    "required": ["headline", "body", "cta"],
    "additionalProperties": False,
}

REVIEWER_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"enum": ["approve", "revise"]},
        "violations": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "rule_id": {"enum": sorted(REVIEWER_RULE_IDS)},
                "severity": {"enum": ["high", "medium"]},
                "quote": {"type": "string"},
                "explanation": {"type": "string"},
                "suggested_fix": {"type": "string"},
            },
            "required": ["rule_id", "severity", "quote", "explanation", "suggested_fix"],
            "additionalProperties": False,
        }},
        "uncertain": {"type": "boolean"},
    },
    "required": ["decision", "violations", "uncertain"],
    "additionalProperties": False,
}


def writer_json_schema():
    """Writer output: the ad (checked by policy) plus the creative concept and visual spec (rendering + review)."""
    from src.agents.creative_spec import ANGLES, EMPHASIS, HOOKS, LAYOUTS, PALETTES, TYPEFACES
    return {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "description": "The marketing goal behind the brief, restated safely in one line."},
            "concept": {"type": "string", "description": "A short name for this creative idea."},
            "angle": {"enum": list(ANGLES)},
            "hook": {"enum": list(HOOKS)},
            "headline": {"type": "string"},
            "body": {"type": "string"},
            "cta": {"type": "string"},
            "visual": {
                "type": "object",
                "properties": {
                    "layout": {"enum": list(LAYOUTS)},
                    "palette": {"enum": list(PALETTES)},
                    "typeface": {"enum": list(TYPEFACES)},
                    "accent": {"enum": list(PALETTES), "description": "Secondary palette for highlights; may equal palette."},
                    "emphasis": {"enum": list(EMPHASIS)},
                    "art_direction": {"type": "string", "description": "One sentence: what the image shows."},
                },
                "required": ["layout", "palette", "typeface", "accent", "emphasis", "art_direction"],
                "additionalProperties": False,
            },
        },
        "required": ["intent", "concept", "angle", "hook", "headline", "body", "cta", "visual"],
        "additionalProperties": False,
    }
