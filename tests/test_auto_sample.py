"""Unit tests for ``_attempt_auto_sample`` — the simctl-sample subprocess wrapper.

The real implementation shells out to ``xcrun simctl spawn <udid> sample <pid>``.
These tests monkeypatch ``subprocess.run`` so we can drive success, timeout, non-
zero exit, and missing-pid paths deterministically.
"""

from __future__ import annotations

import subprocess

import hang_watcher


class _FakeCompleted:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_returns_stack_on_success(monkeypatch):
    captured: dict = {}

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeCompleted(stdout="Sampling process 1234...\n  main thread\n  0x100 foo\n")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    result = hang_watcher._attempt_auto_sample("ABC-123", 1234)

    assert result["kind"] == "simctl-sample"
    assert result["stack"].startswith("Sampling process 1234")
    assert result["symbolicated"] is False
    assert result["reason"] is None
    assert isinstance(result["captured_at_ms"], int)
    assert captured["cmd"][:5] == ["xcrun", "simctl", "spawn", "ABC-123", "sample"]
    assert "1234" in captured["cmd"]
    assert "-mayDie" in captured["cmd"]


def test_missing_udid_short_circuits(monkeypatch):
    called = {"n": 0}

    def _fake_run(*_a, **_kw):
        called["n"] += 1
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    result = hang_watcher._attempt_auto_sample("", 1234)

    assert result["stack"] is None
    assert result["reason"] == "no udid available"
    assert called["n"] == 0


def test_missing_pid_short_circuits(monkeypatch):
    called = {"n": 0}

    def _fake_run(*_a, **_kw):
        called["n"] += 1
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    result = hang_watcher._attempt_auto_sample("ABC-123", 0)

    assert result["stack"] is None
    assert result["reason"] == "no pid available"
    assert called["n"] == 0


def test_timeout_returns_reason(monkeypatch):
    def _fake_run(cmd, **_kw):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=5)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    result = hang_watcher._attempt_auto_sample("ABC-123", 1234)

    assert result["stack"] is None
    assert result["reason"] == "timeout"
    assert result["kind"] == "simctl-sample"


def test_nonzero_exit_returns_reason(monkeypatch):
    def _fake_run(*_a, **_kw):
        return _FakeCompleted(stdout="", stderr="No such process\n", returncode=1)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    result = hang_watcher._attempt_auto_sample("ABC-123", 1234)

    assert result["stack"] is None
    assert "No such process" in result["reason"]


def test_empty_stdout_treated_as_failure(monkeypatch):
    def _fake_run(*_a, **_kw):
        return _FakeCompleted(stdout="   \n", stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    result = hang_watcher._attempt_auto_sample("ABC-123", 1234)

    assert result["stack"] is None
    assert result["reason"]


def test_xcrun_missing_returns_reason(monkeypatch):
    def _fake_run(*_a, **_kw):
        raise FileNotFoundError("xcrun")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    result = hang_watcher._attempt_auto_sample("ABC-123", 1234)

    assert result["stack"] is None
    assert result["reason"] == "xcrun not found"


# === spindump ===


def test_spindump_returns_stack_on_success(monkeypatch):
    captured: dict = {}

    def _fake_run(cmd, **_kw):
        captured["cmd"] = cmd
        return _FakeCompleted(stdout="Process: Foo [1234]\nThread 0x1 main\n  foo()\n")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    result = hang_watcher._attempt_auto_spindump("ABC-123", 1234)

    assert result["kind"] == "spindump"
    assert "Process: Foo" in result["stack"]
    assert result["reason"] is None
    assert captured["cmd"][:5] == ["xcrun", "simctl", "spawn", "ABC-123", "spindump"]
    assert "1234" in captured["cmd"]


def test_spindump_missing_udid_short_circuits(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_a, **_kw: (called.__setitem__("n", called["n"] + 1) or _FakeCompleted()),
    )
    result = hang_watcher._attempt_auto_spindump("", 1234)

    assert result["stack"] is None
    assert result["reason"] == "no udid available"
    assert called["n"] == 0


def test_spindump_timeout_returns_reason(monkeypatch):
    def _fake_run(cmd, **_kw):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=10)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    result = hang_watcher._attempt_auto_spindump("ABC-123", 1234)

    assert result["stack"] is None
    assert result["reason"] == "timeout"
    assert result["kind"] == "spindump"


def test_spindump_nonzero_exit_returns_reason(monkeypatch):
    def _fake_run(*_a, **_kw):
        return _FakeCompleted(stdout="", stderr="No such process\n", returncode=1)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    result = hang_watcher._attempt_auto_spindump("ABC-123", 1234)

    assert result["stack"] is None
    assert "No such process" in result["reason"]


# === atos ===


def test_run_atos_returns_mapping_in_input_order(monkeypatch):
    captured: dict = {}

    def _fake_run(cmd, **_kw):
        captured["cmd"] = cmd
        return _FakeCompleted(
            stdout="Foo.bar() (in MyApp) (Foo.swift:42)\n" "Baz.qux() (in MyApp) (Baz.swift:7)\n"
        )

    monkeypatch.setattr(subprocess, "run", _fake_run)
    resolved = hang_watcher._run_atos("/tmp/MyApp", ["0xAAA", "0xBBB"])

    assert resolved == {
        "0xAAA": "Foo.bar() (in MyApp) (Foo.swift:42)",
        "0xBBB": "Baz.qux() (in MyApp) (Baz.swift:7)",
    }
    assert captured["cmd"][:4] == ["xcrun", "atos", "-o", "/tmp/MyApp"]


def test_run_atos_empty_inputs_short_circuit(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_a, **_kw: (called.__setitem__("n", called["n"] + 1) or _FakeCompleted()),
    )

    assert hang_watcher._run_atos("", ["0xAAA"]) == {}
    assert hang_watcher._run_atos("/tmp/MyApp", []) == {}
    assert called["n"] == 0


def test_run_atos_timeout_returns_empty(monkeypatch):
    def _fake_run(cmd, **_kw):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=10)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    assert hang_watcher._run_atos("/tmp/MyApp", ["0xAAA"]) == {}


def test_run_atos_nonzero_exit_returns_empty(monkeypatch):
    def _fake_run(*_a, **_kw):
        return _FakeCompleted(stdout="", stderr="bad dwarf\n", returncode=1)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    assert hang_watcher._run_atos("/tmp/MyApp", ["0xAAA"]) == {}


def test_resolve_symbolication_target_prefers_dsym(monkeypatch):
    monkeypatch.delenv("IOS_SIM_HANG_APP_BINARY", raising=False)
    monkeypatch.delenv("IOS_SIM_HANG_DSYM", raising=False)
    assert (
        hang_watcher._resolve_symbolication_target("/bin/foo", "/dsyms/foo.dSYM")
        == "/dsyms/foo.dSYM"
    )
    assert hang_watcher._resolve_symbolication_target("/bin/foo", None) == "/bin/foo"


def test_resolve_symbolication_target_env_fallback(monkeypatch):
    monkeypatch.setenv("IOS_SIM_HANG_DSYM", "/env/foo.dSYM")
    assert hang_watcher._resolve_symbolication_target(None, None) == "/env/foo.dSYM"
    monkeypatch.delenv("IOS_SIM_HANG_DSYM")
    monkeypatch.setenv("IOS_SIM_HANG_APP_BINARY", "/env/foo")
    assert hang_watcher._resolve_symbolication_target(None, None) == "/env/foo"


def test_resolve_symbolication_target_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("IOS_SIM_HANG_APP_BINARY", raising=False)
    monkeypatch.delenv("IOS_SIM_HANG_DSYM", raising=False)
    assert hang_watcher._resolve_symbolication_target(None, None) is None
