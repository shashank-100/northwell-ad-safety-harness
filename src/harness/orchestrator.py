"""Owns every state transition and the only path to APPROVED.

Models produce content; this module decides what happens to it.
"""
import time
import uuid

from src.agents import reviewer, writer
from src.harness.context import reviewer_context, writer_context
from src.harness.retry import InfraError
from src.harness.state_machine import Machine, State
from src.harness.tracing import Tracer
from src.policy import deterministic
from src.policy.fingerprint import compute as policy_fingerprint
from src.policy.rules import POLICY_FINGERPRINT, POLICY_VERSION
from src.policy.schemas import InvalidReviewerOutput, parse_reviewer

MAX_ATTEMPTS = 3


class PolicyTampered(Exception):
    pass


def approval_gate(det_results, review):
    """Invariant 9: APPROVED only if every mandatory check passed. review is a validated ReviewerOutput."""
    return (bool(det_results)
            and all(r["passed"] for r in det_results.values())
            and review is not None
            and review.decision == "approve"
            and not review.violations
            and not review.uncertain)


def run(brief_id, brief, run_id=None, tracer=None):
    if policy_fingerprint() != POLICY_FINGERPRINT:  # agents cannot change policy; neither can anything else
        raise PolicyTampered("policy fingerprint mismatch; refusing to run")
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    tracer = tracer or Tracer(run_id)
    m = Machine()
    previous_ad, feedback, history = None, None, []
    total_cost = 0.0

    def finish(state, category, attempt):
        m.to(state)
        result = {"run_id": run_id, "brief_id": brief_id, "brief": brief, "state": state.value,
                  "failure_category": category, "attempts": attempt, "history": history,
                  "final_ad": history[-1]["writer_output"] if history and history[-1]["writer_output"] else None,
                  "final_creative": history[-1]["creative"] if history else None,
                  "cost": round(total_cost, 4), "states": [s.value for s in m.history]}
        tracer.record(kind="result", **{k: v for k, v in result.items() if k != "history"})
        return result

    for attempt in range(1, MAX_ATTEMPTS + 1):
        rec = {"brief_id": brief_id, "attempt_id": attempt, "policy_version": POLICY_VERSION,
               "policy_fingerprint": POLICY_FINGERPRINT, "writer_model": writer.MODEL,
               "writer_prompt_version": writer.PROMPT_VERSION, "writer_output": None, "creative": None,
               "deterministic_results": None, "reviewer_model": None, "reviewer_prompt_version": None,
               "reviewer_feedback": None, "reviewer_raw": None, "decision": None, "tokens": {},
               "latency_ms": {}, "estimated_cost": 0.0}
        history.append(rec)
        m.to(State.GENERATING)

        try:
            w = writer.write(writer_context(brief, previous_ad, feedback), POLICY_VERSION, brief_id=brief_id)
        except InfraError as e:
            rec["decision"] = f"infra:{e.category}"
            tracer.record(kind="attempt", **rec, error=str(e))
            m.to(State.FAILED)
            return finish_failed(m, tracer, run_id, brief_id, brief, history, total_cost, e.category, attempt)
        total_cost += w["cost"]
        rec.update(writer_output=w["data"], creative=w.get("creative"), estimated_cost=w["cost"])
        rec["tokens"]["writer"], rec["latency_ms"]["writer"] = w["tokens"], w["latency_ms"]

        m.to(State.VALIDATING)
        det = deterministic.check(w["data"])
        rec["deterministic_results"] = det
        det_fail = deterministic.failures(det)

        if det_fail:  # invariant 1: the reviewer is never consulted, so it can't override this
            rec["decision"] = "revise:deterministic"
            tracer.record(kind="attempt", **rec)
            category = "INVALID_STRUCTURED_OUTPUT" if not det["OUTPUT_SCHEMA"]["passed"] else "POLICY_VIOLATION"
            if attempt == MAX_ATTEMPTS:
                return finish(State.NEEDS_HUMAN, "RETRY_EXHAUSTED", attempt)
            m.to(State.REVISION_REQUIRED)
            previous_ad = {**w["data"], **(w.get("creative") or {})} if category == "POLICY_VIOLATION" else None
            feedback = det_fail if previous_ad is not None else None
            continue

        m.to(State.REVIEWING)
        rec.update(reviewer_model=reviewer.MODEL, reviewer_prompt_version=reviewer.PROMPT_VERSION)
        try:
            r = reviewer.review(reviewer_context(brief, w["data"], (w.get("creative") or {}).get("visual")),
                                POLICY_VERSION)
        except InfraError as e:
            rec["decision"] = f"infra:{e.category}"
            tracer.record(kind="attempt", **rec, error=str(e))
            m.to(State.FAILED)
            return finish_failed(m, tracer, run_id, brief_id, brief, history, total_cost, e.category, attempt)
        total_cost += r["cost"]
        rec["estimated_cost"] += r["cost"]
        rec["tokens"]["reviewer"], rec["latency_ms"]["reviewer"] = r["tokens"], r["latency_ms"]
        rec["reviewer_raw"] = r["data"]

        try:
            review = parse_reviewer(r["data"], w["data"])
        except InvalidReviewerOutput as e:  # invariant 2: never approve on bad reviewer output
            rec["decision"] = "escalate:invalid_reviewer_output"
            tracer.record(kind="attempt", **rec, error=str(e))
            return finish(State.NEEDS_HUMAN, "INVALID_STRUCTURED_OUTPUT", attempt)
        rec["reviewer_feedback"] = review.model_dump()

        if review.uncertain:  # invariant 4
            rec["decision"] = "escalate:uncertain"
            tracer.record(kind="attempt", **rec)
            return finish(State.NEEDS_HUMAN, "REVIEWER_UNCERTAIN", attempt)

        if approval_gate(det, review):
            rec["decision"] = "approve"
            tracer.record(kind="attempt", **rec)
            return finish(State.APPROVED, None, attempt)

        rec["decision"] = "revise:reviewer"
        tracer.record(kind="attempt", **rec)
        if attempt == MAX_ATTEMPTS:  # invariant 5
            return finish(State.NEEDS_HUMAN, "RETRY_EXHAUSTED", attempt)
        m.to(State.REVISION_REQUIRED)
        previous_ad = {**w["data"], **(w.get("creative") or {})}
        feedback = [v.model_dump() for v in review.violations]

    raise AssertionError("unreachable: loop always returns")


def finish_failed(m, tracer, run_id, brief_id, brief, history, total_cost, category, attempt):
    result = {"run_id": run_id, "brief_id": brief_id, "brief": brief, "state": State.FAILED.value,
              "failure_category": category, "attempts": attempt, "history": history, "final_ad": None,
              "cost": round(total_cost, 4), "states": [s.value for s in m.history]}
    tracer.record(kind="result", **{k: v for k, v in result.items() if k != "history"})
    return result
