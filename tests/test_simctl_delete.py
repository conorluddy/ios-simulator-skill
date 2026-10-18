"""Unit tests for simctl_delete.py: deletions refuse without --yes, never prompt."""

import sys

import pytest
import simctl_delete


@pytest.mark.parametrize(
    "argv, lost",
    [
        (["--udid", "U-1"], "delete U-1 and all its data"),
        (["--all"], "delete all simulators"),
        (["--type", "iPad"], "delete every iPad simulator"),
        (["--old", "2"], "delete older simulators and their data (keeping 2 per type)"),
    ],
)
def test_delete_refuses_without_yes_and_touches_nothing(monkeypatch, capsys, argv, lost):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("nothing should run or prompt before --yes")

    monkeypatch.setattr(simctl_delete.subprocess, "run", fail_if_called)
    monkeypatch.setattr(simctl_delete, "list_simulators", fail_if_called)
    monkeypatch.setattr("builtins.input", fail_if_called)
    monkeypatch.setattr(sys, "argv", ["simctl_delete.py", *argv])

    with pytest.raises(SystemExit) as exit_info:
        simctl_delete.main()

    assert exit_info.value.code == 1
    refusal = capsys.readouterr().err.strip()
    assert refusal.startswith(f"Refusing to {lost}")
    assert "\n" not in refusal


def test_delete_with_yes_runs_simctl_without_prompting(monkeypatch):
    commands = []

    def fake_run(cmd, **kwargs):
        commands.append(cmd)
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(simctl_delete.subprocess, "run", fake_run)
    monkeypatch.setattr(simctl_delete, "resolve_device_identifier", lambda device_id: "U-1")
    monkeypatch.setattr("builtins.input", lambda *args: pytest.fail("must not prompt"))
    monkeypatch.setattr(sys, "argv", ["simctl_delete.py", "--udid", "U-1", "--yes"])

    with pytest.raises(SystemExit) as exit_info:
        simctl_delete.main()

    assert exit_info.value.code == 0
    assert commands == [["xcrun", "simctl", "delete", "U-1"]]
