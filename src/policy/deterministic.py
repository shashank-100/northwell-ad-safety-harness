"""Mechanical rules, enforced in Python. No LLM can override a failure here (invariant 1)."""
import re
from types import MappingProxyType

from pydantic import ValidationError

from src.policy.rules import ALLOWED_CTAS, BODY_MAX, CTA_MAX, HEADLINE_MAX
from src.policy.schemas import Ad

NUMBER_WORDS = r"(?:five|ten|fifteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)"


def normalize(text):
    text = re.sub(r"\b(?:[a-z]\.){2,}", lambda m: m.group(0).replace(".", ""), text.lower())  # f.d.a. -> fda
    text = re.sub(r"[‐-―_]", "-", text)
    return re.sub(r"\s+", " ", text)


PATTERNS = MappingProxyType({
    "FDA_CLAIM": (
        r"\bfda\s*-?\s*(?:approved|cleared|authori[sz]ed|approval)\b",
        r"\b(?:approved|cleared|authori[sz]ed) by (?:the )?fda\b",
    ),
    "GUARANTEED_OUTCOME": (
        r"\bguarantee(?:d|s)?\b",
        r"\bmoney[- ]back\b",
        r"\b100\s*%\s*(?:results|effective|success)",
        r"\b(?:promised|certain|assured) results\b",
    ),
    "WEIGHT_PROMISE": (
        r"\b\d+(?:\.\d+)?\s*-?\s*(?:lbs?|pounds?|kgs?|kilos?|kilograms?)\b",
        rf"\b{NUMBER_WORDS}\s*-?\s*(?:lbs?|pounds?|kgs?|kilos?)\b",
        r"\b\d+\s*%\s*(?:of (?:your )?)?(?:body ?weight|weight)\b",
        r"\b\d+\s+(?:dress|pant|jean) sizes?\b",
    ),
})
REQUIRED = MappingProxyType({
    "RESULTS_DISCLOSURE": r"\bresults (?:may )?vary\b",
    "SAFETY_DISCLOSURE": r"\b(?:important )?safety info(?:rmation)?\b|\bside effects\b",
})


def check(raw):
    """Return {rule_id: {"passed": bool, "quote": str, "detail": str}} for every deterministic rule."""
    results = {}
    try:
        ad = Ad.model_validate(raw)
        if not all(s.strip() for s in (ad.headline, ad.body, ad.cta)):
            raise ValueError("empty field")
    except (ValidationError, ValueError, TypeError) as e:
        return {"OUTPUT_SCHEMA": {"passed": False, "quote": "", "detail": str(e)[:200]}}
    results["OUTPUT_SCHEMA"] = {"passed": True, "quote": "", "detail": ""}

    original = f"{ad.headline}\n{ad.body}\n{ad.cta}"
    text = normalize(original)
    for rule_id, pats in PATTERNS.items():
        hit = next((m for p in pats if (m := re.search(p, text))), None)
        results[rule_id] = {"passed": hit is None, "quote": hit.group(0) if hit else "", "detail": ""}
    for rule_id, pat in REQUIRED.items():
        found = re.search(pat, normalize(ad.body))
        results[rule_id] = {"passed": bool(found), "quote": "", "detail": "" if found else "missing from body"}

    results["HEADLINE_LENGTH"] = _length(ad.headline, HEADLINE_MAX)
    results["BODY_LENGTH"] = _length(ad.body, BODY_MAX)
    cta_ok = ad.cta in ALLOWED_CTAS and len(ad.cta) <= CTA_MAX
    results["CTA_LENGTH"] = {"passed": cta_ok, "quote": ad.cta,
                             "detail": "" if cta_ok else f"must be one of {sorted(ALLOWED_CTAS)}"}
    return results


def _length(value, limit):
    ok = len(value) <= limit
    return {"passed": ok, "quote": "", "detail": "" if ok else f"{len(value)} chars (max {limit})"}


def failures(results):
    return [{"rule_id": rid, "quote": r["quote"], "explanation": r["detail"] or f"violates {rid}"}
            for rid, r in results.items() if not r["passed"]]
