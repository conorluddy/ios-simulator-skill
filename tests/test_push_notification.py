"""Unit tests for push_notification.py: idb --list / --clear command shapes and errors."""

import json
import subprocess
from types import SimpleNamespace

import push_notification
import pytest
from push_notification import IDB_UPGRADE_HINT, PushNotificationSender

UDID = "UDID-1"
BUNDLE = "com.example.app"


@pytest.fixture
def idb_calls(monkeypatch):
    """Capture idb commands; every call succeeds with one listed notification."""
    calls: list[list[str]] = []
    listed = {"title": "Hi", "body": "There", "identifier": "ID-1"}

    def fake_subprocess_run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(stdout=json.dumps(listed) + "\n", stderr="")

    def fake_run_idb(cmd):
        calls.append(cmd)
        return (True, "")

    monkeypatch.setattr(push_notification.subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(push_notification, "run_idb", fake_run_idb)
    return calls


def test_list_runs_idb_notification_list_as_json(idb_calls):
    ok, notifications = PushNotificationSender(UDID).list_delivered(BUNDLE)
    assert ok
    assert idb_calls == [["idb", "notification", "list", BUNDLE, "--json", "--udid", UDID]]
    assert notifications == [{"title": "Hi", "body": "There", "identifier": "ID-1"}]


def test_list_with_no_notifications_returns_empty_list(monkeypatch):
    monkeypatch.setattr(
        push_notification.subprocess,
        "run",
        lambda cmd, **kwargs: SimpleNamespace(stdout="", stderr=""),
    )
    assert PushNotificationSender(UDID).list_delivered(BUNDLE) == (True, [])


def test_clear_runs_idb_notification_clear(idb_calls):
    assert PushNotificationSender(UDID).clear_delivered(BUNDLE) == (True, "")
    assert idb_calls == [["idb", "notification", "clear", BUNDLE, "--udid", UDID]]


def test_list_adds_upgrade_hint_on_pre_1_7_idb(monkeypatch):
    stderr = "idb: error: argument command: invalid choice: 'notification'"

    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(2, cmd, stderr=stderr)

    monkeypatch.setattr(push_notification.subprocess, "run", fake_run)
    ok, error = PushNotificationSender(UDID).list_delivered(BUNDLE)
    assert not ok
    assert stderr in error
    assert IDB_UPGRADE_HINT in error


def test_clear_adds_upgrade_hint_on_pre_1_7_idb(monkeypatch):
    stderr = "idb: error: argument command: invalid choice: 'notification'"
    monkeypatch.setattr(push_notification, "run_idb", lambda cmd: (False, stderr))
    ok, error = PushNotificationSender(UDID).clear_delivered(BUNDLE)
    assert not ok
    assert stderr in error
    assert IDB_UPGRADE_HINT in error


def test_clear_passes_other_idb_errors_through_without_hint(monkeypatch):
    monkeypatch.setattr(push_notification, "run_idb", lambda cmd: (False, "companion not running"))
    assert PushNotificationSender(UDID).clear_delivered(BUNDLE) == (
        False,
        "companion not running",
    )
