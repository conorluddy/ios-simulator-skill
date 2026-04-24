"""
Structured error envelopes for agent-friendly failure handling.

Why: agent-driven scripts fail in predictable ways (no booted sim, element
not found, app not installed). Today each script prints a free-form message
and exits 1. Agents have to parse English to decide whether to retry, fix
something, or give up.

This module defines a small, stable envelope:

    {"ok": false, "error": {"code": "...", "message": "...",
                            "hint": "...", "recovery_cmd": "..."}}

`code` is a stable enum agents can branch on. `message` is the human-readable
detail. `hint` describes the likely cause. `recovery_cmd` (optional) is a
single shell command that, if run, would resolve the failure — the agent
can decide whether to execute it.

Success envelopes mirror the structure: `{"ok": true, "data": {...}}`.

Scripts should:
1. Wrap their main() body in `try: ... except SkillError as e: emit_error(e, json_mode=args.json)`.
2. Raise SkillError(code, message, hint=..., recovery_cmd=...) at known failure points.
3. Use the documented codes below; add new ones to the ERROR_CODES list when you introduce them.

Adoption is incremental — existing scripts can migrate one at a time without
breaking anything.
"""

from __future__ import annotations

import json
import sys

# Stable error codes. When adding one, document it here so agents and
# downstream scripts have a contract to rely on.
ERROR_CODES = {
    "NO_BOOTED_SIM": "No simulator is booted and no UDID was provided.",
    "DEVICE_NOT_FOUND": "Device name or UDID did not match any known simulator.",
    "MULTIPLE_DEVICES": "Multiple devices match; disambiguate with --udid.",
    "IDB_NOT_INSTALLED": "idb-companion is required for this operation but not on PATH.",
    "IDB_CONNECT_FAILED": "idb_companion could not connect to the simulator.",
    "ELEMENT_NOT_FOUND": "No accessibility element matched the query.",
    "ELEMENT_AMBIGUOUS": "Multiple elements matched; use --index or a more specific query.",
    "APP_NOT_INSTALLED": "Bundle ID is not installed on the target simulator.",
    "APP_NOT_RUNNING": "App must be in foreground for this operation.",
    "BUILD_FAILED": "xcodebuild returned a non-zero exit; see xcresult for details.",
    "TEST_FAILED": "One or more XCTest cases failed.",
    "TIMEOUT": "Operation did not complete within the timeout window.",
    "INVALID_ARGS": "Argument validation failed before any side effects.",
    "ENV_MISSING": "A required tool or version is missing from the environment.",
    "PERMISSION_DENIED": "OS or TCC denied the operation.",
    "UNKNOWN": "Unclassified failure; see message.",
}


class SkillError(Exception):
    """A failure that should be reported through the structured envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        hint: str | None = None,
        recovery_cmd: str | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(message)
        if code not in ERROR_CODES:
            # Don't crash on unknown codes — just normalise. Encourages adoption
            # without forcing a docs PR for every new failure mode.
            code = "UNKNOWN"
        self.code = code
        self.message = message
        self.hint = hint
        self.recovery_cmd = recovery_cmd
        self.exit_code = exit_code

    def to_dict(self) -> dict:
        payload: dict = {"code": self.code, "message": self.message}
        if self.hint:
            payload["hint"] = self.hint
        if self.recovery_cmd:
            payload["recovery_cmd"] = self.recovery_cmd
        return {"ok": False, "error": payload}


def emit_error(err: SkillError, *, json_mode: bool = False) -> int:
    """Print an error envelope and return the exit code. Does not call sys.exit."""
    if json_mode:
        print(json.dumps(err.to_dict()), file=sys.stderr)
    else:
        line = f"ERROR [{err.code}]: {err.message}"
        if err.hint:
            line += f"\n  hint: {err.hint}"
        if err.recovery_cmd:
            line += f"\n  recovery: {err.recovery_cmd}"
        print(line, file=sys.stderr)
    return err.exit_code


def emit_success(data: dict | None = None, *, json_mode: bool = False, summary: str | None = None) -> int:
    """Print a success envelope. Use `summary` for the terse human line."""
    if json_mode:
        print(json.dumps({"ok": True, "data": data or {}}))
    elif summary:
        print(summary)
    return 0
