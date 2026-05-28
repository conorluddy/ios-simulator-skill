"""Regression tests for ambiguous booted-device auto-selection.

When more than one simulator is booted, `get_booted_device_udid()` used to
silently return the first match. Gesture/tap commands resolve their target via
this helper, so they could land on a simulator other than the one being watched
(idb reports success on the wrong device, so nothing appears to happen). The fix
keeps the first-match behaviour but emits a stderr warning on ambiguity, and
exposes `get_booted_device_udids()` so callers can detect the multi-device case.
"""

import subprocess

import pytest
from common.device_utils import get_booted_device_udid, get_booted_device_udids

UDID_A = "AAAAAAAA-1111-2222-3333-444444444444"
UDID_B = "BBBBBBBB-5555-6666-7777-888888888888"


def _fake_simctl(stdout: str):
    """Return a subprocess.run stub that yields the given booted-device listing."""

    def _run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")

    return _run


# === get_booted_device_udids ===


def test_lists_all_booted_udids(monkeypatch):
    listing = (
        f"-- iOS 26.2 --\n"
        f"    iPhone 17 Pro ({UDID_A}) (Booted)\n"
        f"    iPad Pro ({UDID_B}) (Booted)\n"
    )
    monkeypatch.setattr(subprocess, "run", _fake_simctl(listing))
    assert get_booted_device_udids() == [UDID_A, UDID_B]


def test_returns_empty_when_none_booted(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_simctl("== Devices ==\n-- iOS 26.2 --\n"))
    assert get_booted_device_udids() == []


def test_returns_empty_when_simctl_fails(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, "simctl")

    monkeypatch.setattr(subprocess, "run", _boom)
    assert get_booted_device_udids() == []


# === get_booted_device_udid ===


def test_single_device_returns_udid_without_warning(monkeypatch, capsys):
    listing = f"-- iOS 26.2 --\n    iPhone 17 Pro ({UDID_A}) (Booted)\n"
    monkeypatch.setattr(subprocess, "run", _fake_simctl(listing))

    assert get_booted_device_udid() == UDID_A
    assert capsys.readouterr().err == ""


def test_multiple_devices_warns_and_picks_first(monkeypatch, capsys):
    listing = f"    iPhone 17 Pro ({UDID_A}) (Booted)\n    iPad Pro ({UDID_B}) (Booted)\n"
    monkeypatch.setattr(subprocess, "run", _fake_simctl(listing))

    assert get_booted_device_udid() == UDID_A
    stderr = capsys.readouterr().err
    assert "2 booted simulators" in stderr
    assert UDID_A in stderr and UDID_B in stderr
    assert "--udid" in stderr


def test_no_device_returns_none(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_simctl("-- iOS 26.2 --\n"))
    assert get_booted_device_udid() is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
