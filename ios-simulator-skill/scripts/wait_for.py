#!/usr/bin/env python3
"""
Wait For — block until a simulator condition becomes true.

Agents repeatedly need "wait until X appears / app is foreground / log line
matches Y". Without this script the pattern is a polling loop in the agent
turn — slow, noisy, and burns context. wait_for.py runs the poll on the
host and returns one line.

Conditions (mutually exclusive — pick one):
  --element <text-or-id>   Wait until an a11y element matches by text/id.
  --element-gone <text>    Wait until a previously-visible element disappears.
  --app-state <state>      Wait until the app reaches a state (foreground|not_running).
                            Requires --bundle-id.
  --log-match <regex>      Wait until a log line matches the regex.
                            Requires --bundle-id (or --any-app to scan all).

Common flags:
  --timeout <seconds>      Default 30.
  --interval <seconds>     Poll interval. Default 0.5 (1.0 for log-match).
  --udid <id>              Override device. Otherwise booted sim is used.
  --json                   Emit structured envelope.

Exit codes:
  0   condition became true
  1   timeout (TIMEOUT error code)
  2   environment / args error

Examples:
  # Wait for the login button after a deep link
  python3 wait_for.py --element "Sign In" --timeout 10

  # Wait for the app to come back to foreground
  python3 wait_for.py --app-state foreground --bundle-id com.example.app

  # Wait until the app logs a specific event
  python3 wait_for.py --log-match "DidFinishLaunching" --bundle-id com.example.app
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from collections.abc import Callable

from common import resolve_udid
from common.errors import SkillError, emit_error, emit_success

# --- Condition checks ---------------------------------------------------------


def _a11y_tree(udid: str) -> list[dict] | None:
    """Return flattened a11y elements, or None if unavailable (e.g. idb missing)."""
    try:
        result = subprocess.run(
            ["idb", "ui", "describe-all", "--udid", udid, "--json", "--nested"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SkillError(
            "IDB_NOT_INSTALLED",
            "idb is required for element-based waits.",
            hint="Install idb-companion to enable UI introspection.",
            recovery_cmd="brew tap facebook/fb && brew install idb-companion",
        ) from exc
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    import json as _json

    try:
        tree = _json.loads(result.stdout)
    except (ValueError, _json.JSONDecodeError):
        return None
    flat: list[dict] = []

    def _walk(node: dict) -> None:
        if isinstance(node, dict):
            flat.append(node)
            for child in node.get("children", []) or []:
                _walk(child)
        elif isinstance(node, list):
            for n in node:
                _walk(n)

    _walk(tree)
    return flat


def check_element_present(udid: str, query: str) -> bool:
    nodes = _a11y_tree(udid)
    if nodes is None:
        return False
    q = query.lower()
    for n in nodes:
        for field in ("AXLabel", "AXValue", "AXUniqueId"):
            v = n.get(field)
            if isinstance(v, str) and q in v.lower():
                return True
    return False


def check_element_gone(udid: str, query: str) -> bool:
    return not check_element_present(udid, query)


def check_app_state(udid: str, bundle_id: str, target_state: str) -> bool:
    """Use simctl to inspect app state."""
    result = subprocess.run(
        ["xcrun", "simctl", "spawn", udid, "launchctl", "list"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    running = bundle_id in result.stdout
    if target_state == "not_running":
        return not running
    if target_state == "foreground":
        # Best-effort: simctl doesn't expose foreground directly; we treat
        # "running and present in a11y tree" as foreground. Falls back to
        # "running" if no idb.
        if not running:
            return False
        nodes = _a11y_tree(udid)
        if nodes is None:
            return running
        return len(nodes) > 0
    raise SkillError(
        "INVALID_ARGS",
        f"Unknown app state: {target_state}",
        hint="Valid states: foreground, not_running",
    )


def make_log_matcher(udid: str, pattern: str, bundle_id: str | None) -> Callable[[], bool]:
    """Stream logs since wait start; check buffer against regex on each poll."""
    rx = re.compile(pattern)
    start = time.time()
    seen: list[str] = []

    def _check() -> bool:
        # Simple periodic capture: ask for everything since `start`. Cheap
        # enough for the kinds of waits agents do.
        elapsed = max(1, int(time.time() - start) + 1)
        cmd = [
            "xcrun",
            "simctl",
            "spawn",
            udid,
            "log",
            "show",
            "--last",
            f"{elapsed}s",
            "--style",
            "compact",
        ]
        if bundle_id:
            cmd += [
                "--predicate",
                f'subsystem == "{bundle_id}" OR processImagePath CONTAINS "{bundle_id}"',
            ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
        except subprocess.TimeoutExpired:
            return False
        for line in result.stdout.splitlines():
            if rx.search(line):
                seen.append(line)
                return True
        return False

    return _check


# --- Polling driver -----------------------------------------------------------


def poll(check: Callable[[], bool], timeout: float, interval: float) -> tuple[bool, float]:
    """Returns (matched, elapsed_seconds)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check():
            return True, time.time() - (deadline - timeout)
        time.sleep(interval)
    return False, timeout


# --- CLI ----------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Block until a simulator condition becomes true.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    cond = parser.add_mutually_exclusive_group(required=True)
    cond.add_argument("--element", metavar="QUERY", help="Wait for a11y element matching text/id")
    cond.add_argument("--element-gone", metavar="QUERY", help="Wait until element disappears")
    cond.add_argument(
        "--app-state", choices=["foreground", "not_running"], help="Wait for app state"
    )
    cond.add_argument("--log-match", metavar="REGEX", help="Wait for log line matching regex")
    parser.add_argument("--bundle-id", help="App bundle id (required for app-state and log-match)")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help="Poll interval (default 0.5s; 1.0s for log-match)",
    )
    parser.add_argument("--udid", help="Override device UDID")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        try:
            udid = resolve_udid(args.udid)
        except RuntimeError as exc:
            raise SkillError(
                "NO_BOOTED_SIM",
                str(exc),
                hint="Boot a simulator first or set $SIMCTL_UDID.",
                recovery_cmd='xcrun simctl boot "iPhone 16 Pro"',
            ) from exc

        # Validate condition-specific args.
        if args.app_state and not args.bundle_id:
            raise SkillError("INVALID_ARGS", "--app-state requires --bundle-id")
        if args.log_match and not args.bundle_id:
            raise SkillError(
                "INVALID_ARGS",
                "--log-match requires --bundle-id",
                hint="Pass --bundle-id to scope the log predicate; otherwise the stream is too noisy to match reliably.",
            )

        if args.element:
            check = lambda: check_element_present(udid, args.element)  # noqa: E731
            label = f'element "{args.element}"'
            interval = args.interval or 0.5
        elif args.element_gone:
            check = lambda: check_element_gone(udid, args.element_gone)  # noqa: E731
            label = f'element-gone "{args.element_gone}"'
            interval = args.interval or 0.5
        elif args.app_state:
            check = lambda: check_app_state(udid, args.bundle_id, args.app_state)  # noqa: E731
            label = f"app-state={args.app_state}"
            interval = args.interval or 0.5
        else:  # log-match
            check = make_log_matcher(udid, args.log_match, args.bundle_id)
            label = f"log /{args.log_match}/"
            interval = args.interval or 1.0

        start = time.time()
        matched, _ = poll(check, args.timeout, interval)
        elapsed = round(time.time() - start, 2)

        if matched:
            return emit_success(
                {"matched": True, "elapsed_s": elapsed, "condition": label},
                json_mode=args.json,
                summary=f"OK: {label} matched in {elapsed}s",
            )

        raise SkillError(
            "TIMEOUT",
            f"{label} did not become true within {args.timeout}s",
            hint="Increase --timeout, or call screen_mapper.py to inspect the current state.",
        )

    except SkillError as e:
        return emit_error(e, json_mode=args.json)


if __name__ == "__main__":
    sys.exit(main())
