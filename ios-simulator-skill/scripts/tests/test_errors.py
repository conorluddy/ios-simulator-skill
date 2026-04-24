"""Contract tests for the structured error envelope.

Locks the on-the-wire shape so future scripts (or refactors) can't silently
break agents that branch on `code`.
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

# Make `common/` a top-level import path so we load errors.py without going
# through common/__init__.py (which transitively imports modules using
# Python 3.12+ syntax — this test file should run under any 3.9+ interpreter).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))

from errors import ERROR_CODES, SkillError, emit_error, emit_success


def test_known_code_preserved():
    err = SkillError("TIMEOUT", "boom")
    assert err.code == "TIMEOUT"
    assert err.to_dict() == {"ok": False, "error": {"code": "TIMEOUT", "message": "boom"}}


def test_unknown_code_normalises_to_unknown():
    err = SkillError("NOT_A_REAL_CODE", "something")
    assert err.code == "UNKNOWN"


def test_envelope_includes_optional_fields():
    err = SkillError(
        "NO_BOOTED_SIM", "no sim", hint="boot one", recovery_cmd="xcrun simctl boot ..."
    )
    payload = err.to_dict()
    assert payload["error"]["hint"] == "boot one"
    assert payload["error"]["recovery_cmd"] == "xcrun simctl boot ..."


def test_envelope_omits_unset_optional_fields():
    payload = SkillError("TIMEOUT", "x").to_dict()
    assert "hint" not in payload["error"]
    assert "recovery_cmd" not in payload["error"]


def test_emit_error_json_writes_to_stderr_and_returns_exit_code():
    buf = io.StringIO()
    with redirect_stderr(buf):
        rc = emit_error(SkillError("TIMEOUT", "x", exit_code=7), json_mode=True)
    assert rc == 7
    parsed = json.loads(buf.getvalue())
    assert parsed["ok"] is False
    assert parsed["error"]["code"] == "TIMEOUT"


def test_emit_error_human_includes_hint_and_recovery():
    buf = io.StringIO()
    with redirect_stderr(buf):
        emit_error(
            SkillError("NO_BOOTED_SIM", "no sim", hint="boot one", recovery_cmd="xcrun ..."),
            json_mode=False,
        )
    out = buf.getvalue()
    assert "[NO_BOOTED_SIM]" in out
    assert "hint: boot one" in out
    assert "recovery: xcrun ..." in out


def test_emit_success_json_envelope():
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = emit_success({"x": 1}, json_mode=True)
    assert rc == 0
    assert json.loads(buf.getvalue()) == {"ok": True, "data": {"x": 1}}


def test_emit_success_human_uses_summary():
    buf = io.StringIO()
    with redirect_stdout(buf):
        emit_success({"x": 1}, json_mode=False, summary="all good")
    assert buf.getvalue().strip() == "all good"


def test_all_documented_codes_have_descriptions():
    # Codes are part of the public contract — every entry must document
    # what it means so agents/users have a stable reference.
    for code, description in ERROR_CODES.items():
        assert isinstance(code, str) and code.isupper()
        assert isinstance(description, str) and description


if __name__ == "__main__":
    # Tiny runner so this file works without pytest installed.
    import traceback

    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except Exception:
                failures += 1
                print(f"  FAIL  {name}")
                traceback.print_exc()
    sys.exit(1 if failures else 0)
