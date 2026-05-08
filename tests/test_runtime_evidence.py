from __future__ import annotations

from app.ml.runtime_evidence import collect_command, collect_safe_environment


def test_collect_command_reports_missing_binary() -> None:
    payload = collect_command(["orvex-definitely-missing-binary"])

    assert payload["status"] == "missing"
    assert payload["returncode"] is None
    assert "not found" in payload["stderr"]


def test_collect_safe_environment_only_includes_allowlisted_keys(monkeypatch) -> None:
    monkeypatch.setenv("AI_MODE", "classifier")
    monkeypatch.setenv("PASSWORD", "do-not-leak")

    payload = collect_safe_environment()

    assert payload == {"AI_MODE": "classifier"}
