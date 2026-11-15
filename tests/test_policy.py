import pytest

from src.policy.deterministic import check, failures

CLEAN = {"headline": "Weight care, on your terms",
         "body": "A licensed provider decides if treatment fits you. Results vary. See safety info.",
         "cta": "See if you qualify"}


def failed(ad):
    return {f["rule_id"] for f in failures(check(ad))}


def with_body(text):
    return {**CLEAN, "body": text + " Results vary. See safety info."}


def test_clean_ad_passes():
    assert failed(CLEAN) == set()


@pytest.mark.parametrize("claim", ["FDA-approved", "FDA approved", "fda  -  approved", "F.D.A. approved",
                                   "approved by the FDA", "FDA cleared", "FDA approval", "FDA‑approved"])
def test_fda_claim_variants(claim):
    assert "FDA_CLAIM" in failed(with_body(f"Our {claim} plan."))


def test_fda_in_headline_caught():
    assert "FDA_CLAIM" in failed({**CLEAN, "headline": "FDA-approved care"})


@pytest.mark.parametrize("claim", ["Guaranteed results", "We guarantee it", "money-back promise", "100% effective"])
def test_guaranteed_outcome(claim):
    assert "GUARANTEED_OUTCOME" in failed(with_body(claim + "."))


@pytest.mark.parametrize("claim", ["Lose 30 lbs", "drop 30lbs", "shed thirty pounds", "lose 5 kg", "lose 15% body weight",
                                   "drop 2 dress sizes"])
def test_weight_promise(claim):
    assert "WEIGHT_PROMISE" in failed(with_body(claim + "."))


@pytest.mark.parametrize("body", ["Care online. See safety info.", "Care online. Results are great. See safety info."])
def test_results_disclosure_required(body):
    assert "RESULTS_DISCLOSURE" in failed({**CLEAN, "body": body})


def test_results_may_vary_accepted():
    assert "RESULTS_DISCLOSURE" not in failed({**CLEAN, "body": "Provider decides. Results may vary. See safety info."})


def test_safety_disclosure_required():
    assert "SAFETY_DISCLOSURE" in failed({**CLEAN, "body": "A provider decides. Results vary."})


def test_disclaimer_does_not_license_prohibited_claim():
    ad = with_body("FDA-approved and guaranteed to work. Lose 20 lbs.")
    assert {"FDA_CLAIM", "GUARANTEED_OUTCOME", "WEIGHT_PROMISE"} <= failed(ad)


def test_lengths():
    assert "HEADLINE_LENGTH" in failed({**CLEAN, "headline": "x" * 41})
    assert "BODY_LENGTH" in failed({**CLEAN, "body": "Results vary. See safety info. " + "x" * 120})
    assert "CTA_LENGTH" in failed({**CLEAN, "cta": "Buy now before it is gone"})


@pytest.mark.parametrize("raw", [None, {}, {"headline": "x", "body": "y"}, {**CLEAN, "extra": 1},
                                 {**CLEAN, "headline": "   "}, {**CLEAN, "cta": 5}])
def test_schema_failures(raw):
    assert failed(raw) == {"OUTPUT_SCHEMA"}


def test_policy_fingerprint_pinned():
    """Any change to rules, limits or patterns must come with a deliberate POLICY_VERSION bump."""
    from src.policy.fingerprint import compute
    from src.policy.rules import POLICY_FINGERPRINT
    assert compute() == POLICY_FINGERPRINT


def test_policy_is_read_only():
    from src.policy import deterministic, rules
    with pytest.raises(TypeError):
        rules.REGISTRY["FDA_CLAIM"] = None
    with pytest.raises(TypeError):
        deterministic.PATTERNS["FDA_CLAIM"] = ()
    with pytest.raises(AttributeError):
        deterministic.PATTERNS["FDA_CLAIM"].append("x")
    with pytest.raises(Exception):
        rules.REGISTRY["FDA_CLAIM"].text = "anything goes"
