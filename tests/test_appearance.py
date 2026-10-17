"""Unit tests for appearance.py: increase-contrast command shape and read-back."""

import subprocess
from types import SimpleNamespace

import appearance
import pytest
from appearance import AppearanceManager

UDID = "UDID-1"


@pytest.fixture
def simctl_calls(monkeypatch):
    """Capture simctl commands; the read-back reports whatever `device_state` holds."""
    calls: list[list[str]] = []
    device_state = {"contrast": "disabled"}

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[-2] == "increase_contrast":
            device_state["contrast"] = cmd[-1]
        return SimpleNamespace(stdout=device_state["contrast"] + "\n", stderr="")

    monkeypatch.setattr(appearance.subprocess, "run", fake_run)
    return SimpleNamespace(calls=calls, device_state=device_state)


def test_contrast_high_enables_increase_contrast_via_simctl(simctl_calls):
    ok, message = AppearanceManager(UDID).set_contrast("high")
    assert ok
    assert message == "Contrast set: high"
    assert simctl_calls.calls[0] == ["xcrun", "simctl", "ui", UDID, "increase_contrast", "enabled"]


def test_contrast_normal_disables_increase_contrast_via_simctl(simctl_calls):
    assert AppearanceManager(UDID).set_contrast("normal")[0]
    assert simctl_calls.calls[0] == ["xcrun", "simctl", "ui", UDID, "increase_contrast", "disabled"]


def test_contrast_reads_state_back_after_setting(simctl_calls):
    AppearanceManager(UDID).set_contrast("high")
    assert simctl_calls.calls[1] == ["xcrun", "simctl", "ui", UDID, "increase_contrast"]


def test_contrast_fails_when_device_reports_unsupported(monkeypatch):
    def fake_run(cmd, **kwargs):
        return SimpleNamespace(stdout="unsupported\n", stderr="")

    monkeypatch.setattr(appearance.subprocess, "run", fake_run)
    ok, message = AppearanceManager(UDID).set_contrast("high")
    assert not ok
    assert "expected enabled" in message
    assert "unsupported" in message


def test_contrast_surfaces_simctl_stderr_on_failure(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr="Invalid device\n")

    monkeypatch.setattr(appearance.subprocess, "run", fake_run)
    assert AppearanceManager(UDID).set_contrast("high") == (False, "Invalid device")


def test_contrast_rejects_unknown_mode_without_running_anything(simctl_calls):
    ok, message = AppearanceManager(UDID).set_contrast("loud")
    assert not ok
    assert "high, normal" in message
    assert simctl_calls.calls == []


def test_reset_restores_normal_contrast(simctl_calls):
    simctl_calls.device_state["contrast"] = "enabled"
    ok, _ = AppearanceManager(UDID).reset()
    assert ok
    assert simctl_calls.device_state["contrast"] == "disabled"
