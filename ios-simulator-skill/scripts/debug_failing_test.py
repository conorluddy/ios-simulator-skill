#!/usr/bin/env python3
"""
Debug Failing Test — Composer

Runs an XCTest and, on failure, captures everything an agent needs to diagnose
it (xcresult errors, app logs, UI hierarchy, screenshot) into one timestamped
bundle. Returns a single summary line with the bundle path.

The point of this script: a failing iOS test is rarely debuggable from the
xcresult alone. You want the simulator state at failure time too — UI tree,
recent logs, a screenshot. Orchestrating that across 4 tools is exactly the
kind of glue work that wastes agent turns. This script does it once.

Usage:
    python3 debug_failing_test.py \\
        --project MyApp.xcodeproj \\
        --scheme MyApp \\
        --test MyAppTests/LoginTests/testInvalidPassword \\
        --bundle-id com.example.MyApp

Output on failure:
    FAIL: testInvalidPassword — bundle: ./debug-20260424-153012/  (3 errors, 142 log lines, ui tree ok, screenshot ok)

Output on success:
    PASS: testInvalidPassword  [xcresult-20260424-153012]
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from common.errors import SkillError, emit_error, emit_success

SCRIPT_DIR = Path(__file__).resolve().parent


def run_script(name: str, args: list[str]) -> tuple[int, str, str]:
    """Invoke a sibling script. Returns (returncode, stdout, stderr)."""
    cmd = [sys.executable, str(SCRIPT_DIR / name), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout, proc.stderr


def run_test(
    project: str | None,
    workspace: str | None,
    scheme: str,
    test_id: str,
    simulator: str | None,
) -> tuple[bool, str | None, str]:
    """
    Run one XCTest via build_and_test.py with --test --suite <id>.

    Returns (passed, xcresult_id, raw_summary_line).
    """
    args = ["--test", "--scheme", scheme, "--suite", test_id, "--json"]
    if workspace:
        args += ["--workspace", workspace]
    elif project:
        args += ["--project", project]
    if simulator:
        args += ["--simulator", simulator]

    rc, out, err = run_script("build_and_test.py", args)
    xcresult_id = None
    passed = rc == 0
    summary = out.strip() or err.strip()
    try:
        data = json.loads(out)
        xcresult_id = data.get("xcresult_id") or data.get("id")
        if "passed" in data:
            passed = bool(data["passed"])
    except (json.JSONDecodeError, ValueError):
        pass
    return passed, xcresult_id, summary


def capture_failure(
    bundle: Path,
    xcresult_id: str | None,
    bundle_id: str | None,
    log_lines: int,
) -> dict:
    """Gather diagnostics into `bundle`. Returns a status dict for the summary."""
    bundle.mkdir(parents=True, exist_ok=True)
    status = {
        "errors": None,
        "log_lines": 0,
        "ui_tree": False,
        "screenshot": False,
    }

    # 1. xcresult errors
    if xcresult_id:
        _rc, out, _err = run_script("build_and_test.py", ["--get-errors", xcresult_id, "--json"])
        (bundle / "xcresult-errors.json").write_text(out)
        try:
            errs = json.loads(out)
            status["errors"] = len(errs) if isinstance(errs, list) else errs.get("count")
        except (json.JSONDecodeError, ValueError):
            status["errors"] = "unparsed"

    # 2. App state (screenshot + UI hierarchy + logs + device info)
    state_args = ["--output", str(bundle / "app-state"), "--log-lines", str(log_lines)]
    if bundle_id:
        state_args += ["--app-bundle-id", bundle_id]
    _rc, _out, _err = run_script("app_state_capture.py", state_args)
    state_dir = bundle / "app-state"
    if state_dir.exists():
        status["ui_tree"] = any(state_dir.glob("*hierarchy*"))
        status["screenshot"] = any(state_dir.glob("*.png"))
        # Count log lines if a logs file exists
        for log_file in state_dir.glob("*log*"):
            try:
                status["log_lines"] = sum(1 for _ in log_file.open())
                break
            except OSError:
                pass

    return status


def summarize(
    test_id: str, passed: bool, status: dict, bundle: Path | None, xcresult_id: str | None
) -> str:
    label = test_id.rsplit("/", 1)[-1]
    if passed:
        tag = f"  [{xcresult_id}]" if xcresult_id else ""
        return f"PASS: {label}{tag}"
    parts = []
    if status["errors"] is not None:
        parts.append(f"{status['errors']} errors")
    parts.append(f"{status['log_lines']} log lines")
    parts.append(f"ui tree {'ok' if status['ui_tree'] else 'missing'}")
    parts.append(f"screenshot {'ok' if status['screenshot'] else 'missing'}")
    return f"FAIL: {label} — bundle: {bundle}/  ({', '.join(parts)})"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an XCTest and, on failure, capture a debug bundle.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--project", help=".xcodeproj path")
    parser.add_argument("--workspace", help=".xcworkspace path (overrides --project)")
    parser.add_argument("--scheme", required=True, help="Build scheme")
    parser.add_argument("--test", required=True, help="Target/Class/method identifier")
    parser.add_argument("--bundle-id", help="App bundle id (for log + UI capture on failure)")
    parser.add_argument("--simulator", help="Simulator name, e.g. 'iPhone 16 Pro'")
    parser.add_argument("--output", help="Bundle directory (default: ./debug-<timestamp>/)")
    parser.add_argument("--log-lines", type=int, default=200, help="Log tail length (default 200)")
    parser.add_argument(
        "--retries", type=int, default=0, help="Retry failed test N times before giving up"
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    try:
        if not args.project and not args.workspace:
            raise SkillError("INVALID_ARGS", "--project or --workspace is required")

        passed = False
        xcresult_id = None
        attempts = 0
        for attempt_idx in range(args.retries + 1):
            attempts = attempt_idx
            passed, xcresult_id, _ = run_test(
                args.project, args.workspace, args.scheme, args.test, args.simulator
            )
            if passed:
                break

        if passed:
            return emit_success(
                {
                    "passed": True,
                    "test": args.test,
                    "attempts": attempts + 1,
                    "xcresult_id": xcresult_id,
                },
                json_mode=args.json,
                summary=summarize(args.test, True, {}, None, xcresult_id),
            )

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bundle = Path(args.output) if args.output else Path.cwd() / f"debug-{timestamp}"
        status = capture_failure(bundle, xcresult_id, args.bundle_id, args.log_lines)

        (bundle / "README.md").write_text(
            f"# Debug bundle — {args.test}\n\n"
            f"- Generated: {timestamp}\n"
            f"- Scheme: {args.scheme}\n"
            f"- Attempts: {attempts + 1}\n"
            f"- xcresult: {xcresult_id or '(none)'}\n\n"
            f"## Contents\n"
            f"- `xcresult-errors.json` — parsed test failures\n"
            f"- `app-state/` — screenshot, UI hierarchy, logs, device info\n"
        )

        # Test failure is a successful run of this script — we did our job
        # (capture diagnostics). Emit a structured envelope but exit 1 to
        # keep shell-level "did the test pass?" semantics.
        payload = {
            "passed": False,
            "test": args.test,
            "attempts": attempts + 1,
            "xcresult_id": xcresult_id,
            "bundle": str(bundle),
            **status,
        }
        if args.json:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "data": payload,
                        "error": {
                            "code": "TEST_FAILED",
                            "message": f"{args.test} failed after {attempts + 1} attempt(s)",
                            "hint": f"Diagnostics in {bundle}/. Inspect xcresult-errors.json and app-state/.",
                        },
                    }
                )
            )
        else:
            print(summarize(args.test, False, status, bundle, xcresult_id))
        return 1

    except SkillError as e:
        return emit_error(e, json_mode=args.json)


if __name__ == "__main__":
    sys.exit(main())
