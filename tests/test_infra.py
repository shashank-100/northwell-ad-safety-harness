"""Infra failures are labelled with the agent that actually failed, and retried separately."""
import json
import subprocess

import pytest

from src.agents import cli
from src.harness.retry import InfraError, with_retries


@pytest.mark.parametrize("role,category", [("writer", "WRITER_FAILURE"), ("reviewer", "REVIEWER_FAILURE")])
def test_non_json_labelled_by_role(monkeypatch, role, category):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "oops", "boom"))
    with pytest.raises(InfraError) as e:
        cli.call("m", "s", "u", {}, role=role)
    assert e.value.category == category


@pytest.mark.parametrize("role", ["writer", "reviewer"])
def test_is_error_labelled_by_role(monkeypatch, role):
    out = json.dumps({"is_error": True, "result": "overloaded"})
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, out, ""))
    with pytest.raises(InfraError) as e:
        cli.call("m", "s", "u", {}, role=role)
    assert e.value.category == f"{role.upper()}_FAILURE"


def test_timeout(monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired("claude", 1)
    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(InfraError) as e:
        cli.call("m", "s", "u", {}, role="reviewer")
    assert e.value.category == "TIMEOUT"


def test_role_required():
    with pytest.raises(TypeError):
        cli.call("m", "s", "u", {})


def test_retries_then_succeeds():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise InfraError("REVIEWER_FAILURE", "x")
        return "ok"
    assert with_retries(flaky, backoff_s=0) == "ok" and len(calls) == 3


def test_retries_exhausted_reraises():
    def always():
        raise InfraError("TIMEOUT", "x")
    with pytest.raises(InfraError):
        with_retries(always, attempts=2, backoff_s=0)
