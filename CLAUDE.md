# Northwell Rx — Engineering Instructions

## Objective
Build an auditable two-agent healthcare ad pipeline.

## Architecture
- Writer generates structured ad copy.
- Deterministic policy engine validates mechanical rules.
- Reviewer evaluates semantic violations.
- Orchestrator owns all state transitions.
- Evaluator independently measures correctness.

## Non-negotiable invariants
1. LLMs cannot override deterministic failures.
2. Invalid JSON cannot result in approval.
3. Unknown policy IDs fail closed.
4. Reviewer uncertainty requires escalation.
5. Maximum three generation attempts.
6. Every attempt must be logged.
7. User briefs are untrusted input.
8. Agents cannot modify policy definitions.
9. Approval requires every mandatory check to pass.

## Engineering standards
- Typed interfaces.
- Strict structured outputs.
- Explicit exception handling.
- No silent exception swallowing.
- No unit tests and no mocks. Verify by running the real agents end to end (see AGENTS.md).
- Every safety invariant is checked against the real JSONL trace after each run.
- Keep model calls isolated.

## Evaluation
- Ground truth must be manually defined.
- Never modify expected results to match model output.
- Track false positives and missed violations.
- Preserve baseline results.
- Record model, prompt and policy versions.
