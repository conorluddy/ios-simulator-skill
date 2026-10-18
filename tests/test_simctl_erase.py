"""Unit tests for simctl_erase.py: erases refuse without --yes (AGENTS.md Principle 10)."""

import sys

import pytest
import simctl_erase


@pytest.mark.parametrize(
    "argv, lost",
    [
        (["--udid", "U-1"], "erase U-1"),
        (["--all"], "erase all simulators"),
        (["--type", "iPhone"], "erase every iPhone simulator"),
        (["--booted"], "erase every booted simulator"),
    ],
)
def test_erase_refuses_without_yes_and_touches_nothing(monkeypatch, capsys, argv, lost):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("nothing should run before --yes")

    monkeypatch.setattr(simctl_erase.subprocess, "run", fail_if_called)
    monkeypatch.setattr(simctl_erase, "list_simulators", fail_if_called)
    monkeypatch.setattr(sys, "argv", ["simctl_erase.py", *argv])

    with pytest.raises(SystemExit) as exit_info:
        simctl_erase.main()

    assert exit_info.value.code == 1
    refusal = capsys.readouterr().err.strip()
    assert refusal.startswith(f"Refusing to {lost}")
    assert refusal.endswith("re-run with --yes")
    assert "\n" not in refusal


def test_erase_with_yes_proceeds(monkeypatch):
    erased = []

    class FakeEraser:
        def __init__(self, udid):
            self.udid = udid

        def erase(self, verify, timeout_seconds):
            erased.append(self.udid)
            return True, "Device erased"

    monkeypatch.setattr(simctl_erase, "SimulatorEraser", FakeEraser)
    monkeypatch.setattr(simctl_erase, "resolve_device_identifier", lambda device_id: "U-1")
    monkeypatch.setattr(sys, "argv", ["simctl_erase.py", "--udid", "U-1", "--yes"])

    with pytest.raises(SystemExit) as exit_info:
        simctl_erase.main()

    assert exit_info.value.code == 0
    assert erased == ["U-1"]
