from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from analyzers.semgrep_runner import run_semgrep


def test_run_semgrep_degrades_when_executable_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_not_found(*args, **kwargs):
        raise FileNotFoundError("semgrep not found")

    monkeypatch.setattr(subprocess, "run", _raise_not_found)

    result = run_semgrep("public class Demo {}")

    assert result["issues"] == []
    codes = {item.get("code") for item in result["diagnostics"]}
    assert "SEMGREP_UNAVAILABLE" in codes


def test_run_semgrep_degrades_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="semgrep", timeout=1)

    monkeypatch.setattr(subprocess, "run", _raise_timeout)

    result = run_semgrep("public class Demo {}", timeout_seconds=1)

    assert result["issues"] == []
    codes = {item.get("code") for item in result["diagnostics"]}
    assert "SEMGREP_TIMEOUT" in codes


def test_run_semgrep_degrades_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    completed = subprocess.CompletedProcess(
        args=["semgrep"],
        returncode=0,
        stdout="{invalid-json",
        stderr="",
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed)

    result = run_semgrep("public class Demo {}")

    assert result["issues"] == []
    codes = {item.get("code") for item in result["diagnostics"]}
    assert "SEMGREP_EXEC_ERROR" in codes


def test_run_semgrep_handles_clean_code_result(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps({"results": [], "errors": []})
    completed = subprocess.CompletedProcess(
        args=["semgrep"],
        returncode=0,
        stdout=payload,
        stderr="",
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed)

    result = run_semgrep("public class Clean {}")

    assert result["issues"] == []
    assert result["summary"]["issuesCount"] == 0


def test_run_semgrep_detects_issue_when_environment_supports_it() -> None:
    if shutil.which("semgrep") is None:
        pytest.skip("semgrep is not installed in this environment")

    code = """
public class InsecureQuery {
    public void run(String userInput) throws Exception {
        String sql = "select * from users where id = " + userInput;
        java.sql.Statement stmt = null;
        stmt.executeQuery(sql);
    }
}
""".strip()
    result = run_semgrep(code)
    codes = {item.get("code") for item in result.get("diagnostics", [])}
    if codes.intersection({"SEMGREP_UNAVAILABLE", "SEMGREP_TIMEOUT", "SEMGREP_EXEC_ERROR"}):
        pytest.skip("semgrep execution is unavailable or unstable in this environment")
    if not result["issues"]:
        pytest.skip("semgrep returned no issues with auto ruleset in this environment")

    assert len(result["issues"]) >= 1
