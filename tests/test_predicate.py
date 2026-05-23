"""Regression tests for #83 — `--bundle-id` must not narrow the os_log predicate.

The default hang predicate matches RunningBoard / SpringBoard / watchdog events
that originate outside the target app's process. Pre-#83, passing `--bundle-id`
ANDed `process == <app>` into the predicate and silently dropped the bulk of
useful hang signal. This module locks down that the predicate stays simulator-
global and that bundle filtering is applied post-parse instead.
"""

import os

import pytest

import hang_watcher


# === predicate composition ===


def test_default_predicate_includes_runningboard_clause():
    predicate = hang_watcher._resolve_predicate(None)
    assert 'com.apple.runningboard' in predicate
    assert 'Hang detected' in predicate


def test_cli_override_takes_precedence():
    predicate = hang_watcher._resolve_predicate('custom == 1')
    assert predicate == 'custom == 1'


def test_env_var_takes_precedence_over_default(monkeypatch):
    monkeypatch.setenv('IOS_SIM_HANG_PREDICATE', 'env == 1')
    assert hang_watcher._resolve_predicate(None) == 'env == 1'


def test_predicate_never_narrows_for_bundle_id():
    """The fix: `_resolve_predicate` no longer accepts a bundle_id arg at all.

    Confirming via signature inspection — adding the param back would resurrect
    the bug.
    """
    import inspect

    params = inspect.signature(hang_watcher._resolve_predicate).parameters
    assert list(params) == ['predicate'], (
        f"_resolve_predicate must take only `predicate`, got {list(params)}. "
        "Adding bundle_id back will re-narrow the predicate and drop RunningBoard events."
    )


# === post-parse bundle filter ===


def test_matches_bundle_matches_app_suffix():
    event = {'process': 'grapla', 'message': 'Hang detected'}
    assert hang_watcher.matches_bundle(event, 'com.conorluddy.grapla') is True


def test_matches_bundle_is_case_insensitive():
    event = {'process': 'Grapla', 'message': 'x'}
    assert hang_watcher.matches_bundle(event, 'com.conorluddy.GRAPLA') is True


def test_matches_bundle_rejects_other_process():
    event = {'process': 'runningboardd', 'message': 'x'}
    assert hang_watcher.matches_bundle(event, 'com.conorluddy.grapla') is False


def test_matches_bundle_handles_missing_process():
    event = {'message': 'x'}
    assert hang_watcher.matches_bundle(event, 'com.example.app') is False
