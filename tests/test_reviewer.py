"""Reviewer output is validated against the schema, the reviewer's allowed rule ids, and the ad itself."""
import pytest

from src.policy.rules import REGISTRY, REVIEWER_RULE_IDS
from src.policy.schemas import REVIEWER_JSON_SCHEMA, InvalidReviewerOutput, parse_reviewer

AD = {"headline": "Get your dream body", "body": "A provider decides. Results vary. See safety info.",
      "cta": "Learn more"}


def v(rule_id="IMPLIED_OUTCOME", quote="dream body"):
    return {"rule_id": rule_id, "severity": "high", "quote": quote, "explanation": "x", "suggested_fix": "y"}


def test_valid_revise():
    out = parse_reviewer({"decision": "revise", "violations": [v()], "uncertain": False}, AD)
    assert out.violations[0].rule_id == "IMPLIED_OUTCOME"


def test_valid_approve():
    assert parse_reviewer({"decision": "approve", "violations": [], "uncertain": False}, AD).decision == "approve"


@pytest.mark.parametrize("rule_id", sorted(r for r in REGISTRY if r not in REVIEWER_RULE_IDS))
def test_reviewer_cannot_cite_deterministic_rules(rule_id):
    with pytest.raises(InvalidReviewerOutput, match="reviewer cannot cite"):
        parse_reviewer({"decision": "revise", "violations": [v(rule_id)], "uncertain": False}, AD)


def test_unknown_rule_id_fails_closed():
    with pytest.raises(InvalidReviewerOutput):
        parse_reviewer({"decision": "revise", "violations": [v("MADE_UP")], "uncertain": False}, AD)


def test_json_schema_enum_matches_reviewer_rules():
    enum = REVIEWER_JSON_SCHEMA["properties"]["violations"]["items"]["properties"]["rule_id"]["enum"]
    assert set(enum) == REVIEWER_RULE_IDS


def test_quote_must_appear_verbatim_in_ad():
    with pytest.raises(InvalidReviewerOutput, match="quote not found"):
        parse_reviewer({"decision": "revise", "violations": [v(quote="lose weight fast")], "uncertain": False}, AD)


def test_empty_quote_rejected():
    with pytest.raises(InvalidReviewerOutput):
        parse_reviewer({"decision": "revise", "violations": [v(quote="")], "uncertain": False}, AD)


@pytest.mark.parametrize("raw", [
    None, "approve", {}, {"decision": "approve"},
    {"decision": "yes", "violations": [], "uncertain": False},
    {"decision": "approve", "violations": [], "uncertain": False, "override": True},
    {"decision": "approve", "violations": [v()], "uncertain": False},
    {"decision": "revise", "violations": [], "uncertain": False},
])
def test_malformed_output_rejected(raw):
    with pytest.raises(InvalidReviewerOutput):
        parse_reviewer(raw, AD)
