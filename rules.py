"""Compliance rules for Northwell Rx ads.

Deterministic checks run first: free, exact, can't be argued with.
The LLM judge only sees rules that need judgment.
"""
import re

ALLOWED_CTAS = {"Start your visit", "See if you qualify", "Learn more"}


def _text(ad):
    return f"{ad.get('headline', '')} {ad.get('body', '')}"


def r1_fda(ad):
    m = re.search(r"\bFDA[- ]approved\b", _text(ad), re.I)
    if m:
        return {"rule_id": "R1", "quote": m.group(0),
                "fix": "Compounded medications are not FDA-approved. Remove the claim."}


def r2_guarantee(ad):
    m = re.search(r"\bguarantee[ds]?\b|\b\d+\s*(lbs?|pounds|kg)\b", _text(ad), re.I)
    if m:
        return {"rule_id": "R2", "quote": m.group(0),
                "fix": "No guarantees or specific outcome numbers. Describe the program, not the result."}


def r3_results_vary(ad):
    if not re.search(r"results (may )?vary", _text(ad), re.I):
        return {"rule_id": "R3", "quote": "",
                "fix": "Add 'Results vary.' to the body."}


def r5_safety(ad):
    if not re.search(r"safety info|side effects", _text(ad), re.I):
        return {"rule_id": "R5", "quote": "",
                "fix": "Reference important safety information, e.g. 'See safety info.'"}


def r8_schema(ad):
    problems = []
    if len(ad.get("headline", "")) > 40:
        problems.append(f"headline is {len(ad['headline'])} chars (max 40)")
    if len(ad.get("body", "")) > 125:
        problems.append(f"body is {len(ad['body'])} chars (max 125)")
    if ad.get("cta") not in ALLOWED_CTAS:
        problems.append(f"cta must be one of {sorted(ALLOWED_CTAS)}")
    if problems:
        return {"rule_id": "R8", "quote": "", "fix": "; ".join(problems)}


DETERMINISTIC = [r1_fda, r2_guarantee, r3_results_vary, r5_safety, r8_schema]


def check(ad):
    return [v for fn in DETERMINISTIC if (v := fn(ad))]


JUDGE_RULES = """\
R2  No implied guaranteed or specific outcomes, even without numbers ("melt the fat away", "finally be thin").
R4  The ad must make clear a licensed provider decides whether treatment is appropriate.
R6  No before/after framing or transformation timelines ("you in 90 days").
R7  Nothing that targets or implies minors (students, teens, school events). No body-shaming language.\
"""

ALL_RULES = """\
R1  Never say "FDA-approved" (our medications are compounded).
R2  No guarantees, no specific outcome numbers, no implied guaranteed results.
R3  Body must include "Results vary."
R4  Make clear a licensed provider decides if treatment is appropriate.
R5  Reference important safety information (e.g. "See safety info.").
R6  No before/after framing or transformation timelines.
R7  Never target or imply minors. No body-shaming.
R8  headline <= 40 chars, body <= 125 chars, cta exactly one of: "Start your visit", "See if you qualify", "Learn more".\
"""
