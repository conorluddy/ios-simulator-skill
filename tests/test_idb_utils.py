"""Unit tests for common.idb_utils: run_idb outcomes and screen-size fallback."""

import subprocess

from common import device_utils, idb_utils


def test_run_idb_returns_stderr_on_failure(monkeypatch):
    def fail(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr="Connection refused\n")

    monkeypatch.setattr(idb_utils.subprocess, "run", fail)
    assert idb_utils.run_idb(["idb", "ui", "tap", "1", "2"]) == (False, "Connection refused")


def test_run_idb_reports_missing_binary(monkeypatch):
    def missing(cmd, **kwargs):
        raise FileNotFoundError("idb")

    monkeypatch.setattr(idb_utils.subprocess, "run", missing)
    ok, error = idb_utils.run_idb(["idb"])
    assert not ok
    assert "sim_health_check" in error


def test_screen_size_falls_back_instead_of_exiting(monkeypatch):
    def fail(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr="boom")

    monkeypatch.setattr(device_utils.subprocess, "run", fail)
    assert idb_utils.get_screen_size("U") == (390, 844)


def test_capability_probe_reads_help_text(monkeypatch):
    idb_utils._ui_help.cache_clear()
    monkeypatch.setattr(
        idb_utils.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, stdout="  --value VALUE"),
    )
    assert idb_utils.idb_supports_set_value()
    idb_utils._ui_help.cache_clear()


def test_capability_probe_is_false_for_unknown_command(monkeypatch):
    idb_utils._ui_help.cache_clear()
    monkeypatch.setattr(
        idb_utils.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(
            cmd, 2, stdout="", stderr="invalid choice"
        ),
    )
    assert not idb_utils.idb_supports_set_value()
    idb_utils._ui_help.cache_clear()


def test_capability_probe_is_false_without_idb(monkeypatch):
    idb_utils._ui_help.cache_clear()

    def missing(cmd, **kwargs):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(idb_utils.subprocess, "run", missing)
    assert not idb_utils.idb_supports_set_value()
    idb_utils._ui_help.cache_clear()
