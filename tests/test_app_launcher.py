"""Unit tests for app_launcher launch arguments and environment variables."""

from unittest import mock

import app_launcher
from app_launcher import AppLauncher


def _run_launch(monkeypatch, **launch_kwargs):
    """Invoke AppLauncher.launch with subprocess.run mocked; return the call."""
    completed = mock.Mock(stdout="com.example.app: 4242")
    runner = mock.Mock(return_value=completed)
    monkeypatch.setattr(app_launcher.subprocess, "run", runner)
    success, pid = AppLauncher(udid="ABC123").launch("com.example.app", **launch_kwargs)
    assert success is True
    assert pid == 4242
    return runner.call_args


def test_launch_appends_trailing_args(monkeypatch):
    call = _run_launch(monkeypatch, launch_args=["-uiTestingMode", "1"])
    cmd = call.args[0]
    # Trailing args land after the bundle id, in order.
    assert cmd[-3:] == ["com.example.app", "-uiTestingMode", "1"]
    # No app env supplied -> inherit parent env.
    assert call.kwargs["env"] is None


def test_launch_injects_simctl_child_env(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    call = _run_launch(monkeypatch, env_vars={"DEBUG": "1"})
    run_env = call.kwargs["env"]
    assert run_env["SIMCTL_CHILD_DEBUG"] == "1"
    # Parent env is preserved alongside the injected vars.
    assert run_env["PATH"] == "/usr/bin"


def test_launch_without_extras_inherits_env(monkeypatch):
    call = _run_launch(monkeypatch)
    cmd = call.args[0]
    assert cmd[-1] == "com.example.app"
    assert call.kwargs["env"] is None
