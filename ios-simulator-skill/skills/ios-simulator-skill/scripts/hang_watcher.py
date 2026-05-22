#!/usr/bin/env python3
"""
iOS Simulator Hang Watcher

Live os_log hang stream from iOS simulators. Parses hang events from Apple's
RunningBoard subsystem and UIKit/SwiftUI thread-stall reports into structured
records with timestamp, PID, process, and duration estimate.

Predicate covers:
- Major hangs: com.apple.runningboard subsystem (process kills / watchdog)
- Micro-hangs: SwiftUI / UIKit "Hang detected" messages
- Tunable via env var: IOS_SIM_HANG_PREDICATE

Usage Examples:
    # Watch for hangs for 60 seconds (default mode)
    python scripts/hang_watcher.py --watch --duration 60

    # Watch a specific app
    python scripts/hang_watcher.py --watch --bundle-id com.example.app

    # Show hangs from the last 5 minutes as JSON
    python scripts/hang_watcher.py --since 5m --json

    # Override predicate
    IOS_SIM_HANG_PREDICATE='subsystem == "com.apple.runningboard"' \\
        python scripts/hang_watcher.py --watch --duration 30
"""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Resolve imports whether run from repo root or scripts/ directory
_script_dir = str(Path(__file__).resolve().parent)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from common.cache_utils import ProgressiveCache  # noqa: E402
from common.device_utils import resolve_device_identifier  # noqa: E402

# === CONSTANTS ===

# Default predicate: catches RunningBoard kills + SwiftUI/UIKit micro-hangs.
# Override with env var IOS_SIM_HANG_PREDICATE for custom tuning.
DEFAULT_HANG_PREDICATE = (
    '(subsystem == "com.apple.runningboard") '
    'OR (eventMessage CONTAINS "Hang detected") '
    'OR ((eventMessage CONTAINS[c] "main thread") AND (eventMessage CONTAINS[c] "hang"))'
)

# Patterns for parsing duration estimates from hang messages.
# Matches: "2.5s", "250ms", "1.2 seconds", "800 milliseconds"
_DURATION_PATTERNS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*s(?:econds?)?(?!\w)", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*ms(?:illiseconds?)?(?!\w)", re.IGNORECASE),
]

# os_log stream output columns:
# 2024-01-15 10:23:45.123456-0800 0x1234 Default   0x0 1234 0 ProcessName: Message
_LOG_LINE_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+(?:[+-]\d{4})?)"  # timestamp
    r"\s+0x[\da-f]+"  # thread
    r"\s+\S+"  # type
    r"\s+0x[\da-f]+"  # activity
    r"\s+(\d+)"  # PID
    r"\s+\d+"  # TTL
    r"\s+([^:]+):"  # process name
    r"\s*(.*)",  # message
    re.IGNORECASE,
)


def _compute_start_timestamp(duration_str: str) -> str:
    """Parse duration string and return ISO-8601 start timestamp.

    Args:
        duration_str: Duration like '30s', '5m', '1h'.

    Raises:
        ValueError: If the format is unrecognised.
    """
    match = re.match(r"(\d+)([smh])", duration_str.lower())
    if not match:
        raise ValueError(
            f"Invalid duration format: {duration_str!r}. Use format like '30s', '5m', '1h'."
        )

    value, unit = match.groups()
    seconds = int(value) * {"s": 1, "m": 60, "h": 3600}[unit]
    start = datetime.now() - timedelta(seconds=seconds)
    return start.strftime("%Y-%m-%d %H:%M:%S")


# === HANG WATCHER ===


class HangWatcher:
    """Watch for iOS simulator hang events via os_log stream."""

    def __init__(self, udid: str | None = None):
        """Initialize hang watcher.

        Args:
            udid: Device UDID. Resolves to booted simulator if None.
        """
        self.udid = udid
        self.hang_events: list[dict] = []
        self.interrupted = False
        self._process: subprocess.Popen | None = None
        self._cache = ProgressiveCache()

    # === PUBLIC API ===

    def watch(
        self,
        duration_seconds: int | None = None,
        bundle_id: str | None = None,
        predicate: str | None = None,
        verbose: bool = False,
        json_mode: bool = False,
    ) -> bool:
        """Stream hang events live from the simulator.

        Runs `xcrun simctl spawn <udid> log stream --predicate <pred>` and
        parses each line into a structured hang event. Stops after
        duration_seconds or on Ctrl-C.

        Args:
            duration_seconds: Stop after N seconds. None = run until Ctrl-C.
            bundle_id: Filter events to a specific app bundle ID.
            predicate: Custom log predicate. Falls back to env var then default.
            verbose: Emit raw log lines alongside structured events.
            json_mode: Emit JSON objects per line instead of formatted text.

        Returns:
            True if stream ran without fatal errors.
        """
        resolved_udid = self._resolve_udid()
        effective_predicate = self._resolve_predicate(predicate, bundle_id)
        cmd = self._build_stream_cmd(resolved_udid, effective_predicate)

        if verbose or not json_mode:
            print(
                f"Watching for hangs on {resolved_udid}",
                file=sys.stderr,
            )
            if bundle_id:
                print(f"Filter: {bundle_id}", file=sys.stderr)
            print(f"Predicate: {effective_predicate}", file=sys.stderr)

        self._register_signal_handler()

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            start_time = datetime.now()

            for raw_line in iter(self._process.stdout.readline, ""):
                if not raw_line:
                    break

                line = raw_line.rstrip()
                event = self._parse_line(line)

                if event:
                    if bundle_id and not self._matches_bundle(event, bundle_id):
                        continue

                    self.hang_events.append(event)

                    if json_mode:
                        print(json.dumps(event))
                        sys.stdout.flush()
                    else:
                        print(self._format_event(event))
                        if verbose:
                            print(f"  raw: {line}")

                elif verbose and line.strip():
                    print(f"  [skip] {line}", file=sys.stderr)

                if (
                    duration_seconds
                    and (datetime.now() - start_time).total_seconds() >= duration_seconds
                ):
                    break

                if self.interrupted:
                    break

            # Terminate before wait — log stream never self-exits on duration elapsed.
            if self._process and self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            return True

        except Exception as error:
            print(f"Error streaming hang events: {error}", file=sys.stderr)
            return False

        finally:
            if self._process and self._process.poll() is None:
                self._process.terminate()

    def show_since(
        self,
        since_duration: str,
        bundle_id: str | None = None,
        predicate: str | None = None,
        verbose: bool = False,
        json_mode: bool = False,
    ) -> bool:
        """Show historical hang events using `log show`.

        Args:
            since_duration: Duration string like "5m", "1h", "30s".
            bundle_id: Filter to a specific app bundle ID.
            predicate: Custom log predicate.
            verbose: Include raw log lines.
            json_mode: Emit JSON objects per line.

        Returns:
            True if command ran without fatal errors.
        """
        resolved_udid = self._resolve_udid()
        effective_predicate = self._resolve_predicate(predicate, bundle_id)
        start_timestamp = self._compute_start_timestamp(since_duration)
        cmd = self._build_show_cmd(resolved_udid, effective_predicate, start_timestamp)

        if verbose or not json_mode:
            print(f"Showing hangs since {start_timestamp}", file=sys.stderr)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )

            for raw_line in result.stdout.splitlines():
                line = raw_line.rstrip()
                event = self._parse_line(line)

                if event:
                    if bundle_id and not self._matches_bundle(event, bundle_id):
                        continue

                    self.hang_events.append(event)

                    if json_mode:
                        print(json.dumps(event))
                    else:
                        print(self._format_event(event))
                        if verbose:
                            print(f"  raw: {line}")

            return True

        except subprocess.TimeoutExpired:
            print("Error: log show timed out after 60s", file=sys.stderr)
            return False
        except Exception as error:
            print(f"Error fetching historical hangs: {error}", file=sys.stderr)
            return False

    def get_summary(self) -> str:
        """Return token-efficient summary of captured hang events."""
        total = len(self.hang_events)
        if total == 0:
            return "No hang events detected."

        processes = {}
        for event in self.hang_events:
            proc = event.get("process", "unknown")
            processes[proc] = processes.get(proc, 0) + 1

        top = sorted(processes.items(), key=lambda x: x[1], reverse=True)[:5]
        top_str = ", ".join(f"{p}({c})" for p, c in top)
        return f"Hangs detected: {total} | Processes: {top_str}"

    def get_json_output(self) -> dict:
        """Return full results as a JSON-serialisable dict."""
        return {
            "hang_events": self.hang_events,
            "summary": {
                "total_hangs": len(self.hang_events),
                "processes": list({e.get("process") for e in self.hang_events}),
            },
        }

    def save_to_cache(self) -> str:
        """Persist hang archive to progressive cache and return cache_id."""
        return self._cache.save(self.get_json_output(), "hang-watcher")

    # === PRIVATE HELPERS ===

    def _resolve_udid(self) -> str:
        """Resolve UDID from stored value or booted device."""
        identifier = self.udid or "booted"
        try:
            return resolve_device_identifier(identifier)
        except RuntimeError as error:
            print(f"Error: {error}", file=sys.stderr)
            sys.exit(1)

    def _resolve_predicate(self, override: str | None, bundle_id: str | None) -> str:
        """Return the active log predicate.

        Priority: CLI --predicate > IOS_SIM_HANG_PREDICATE env var > DEFAULT.
        Bundle ID is always ANDed in as a predicate clause when provided, regardless
        of whether a custom predicate source is in use.
        """
        base = override or os.getenv("IOS_SIM_HANG_PREDICATE") or DEFAULT_HANG_PREDICATE

        if bundle_id:
            # Use /.app/ path segment for precise matching — avoids substring collisions
            # (e.g. "Maps" matching "MapsExtension"). Falls back to process name.
            app_name = bundle_id.rsplit(".", maxsplit=1)[-1]
            bundle_clause = (
                f'(processImagePath CONTAINS "/{app_name}.app/" OR process == "{app_name}")'
            )
            base = f"({base}) AND {bundle_clause}"

        return base

    def _build_stream_cmd(self, udid: str, predicate: str) -> list[str]:
        """Build xcrun simctl spawn log stream command."""
        return [
            "xcrun",
            "simctl",
            "spawn",
            udid,
            "log",
            "stream",
            "--predicate",
            predicate,
        ]

    def _build_show_cmd(self, udid: str, predicate: str, start: str) -> list[str]:
        """Build xcrun simctl spawn log show command for historical queries."""
        return [
            "xcrun",
            "simctl",
            "spawn",
            udid,
            "log",
            "show",
            "--predicate",
            predicate,
            "--start",
            start,
        ]

    def _parse_line(self, line: str) -> dict | None:
        """Parse a single os_log line into a hang event dict.

        Returns None if the line doesn't match expected format or isn't hang-related.
        """
        if not line.strip():
            return None

        match = _LOG_LINE_PATTERN.match(line)
        if not match:
            return None

        timestamp_str, pid_str, process_name, message = match.groups()
        message = message.strip()

        # Only surface lines that look like hang events
        if not self._is_hang_message(message):
            return None

        event: dict = {
            "timestamp": timestamp_str.strip(),
            "pid": int(pid_str),
            "process": process_name.strip(),
            "message": message,
        }

        duration_ms = self._extract_duration_ms(message)
        if duration_ms is not None:
            event["duration_estimate_ms"] = duration_ms

        return event

    def _is_hang_message(self, message: str) -> bool:
        """Return True if the message content describes a hang event."""
        lower = message.lower()
        return (
            "hang" in lower
            or "stall" in lower
            or "unresponsive" in lower
            or "watchdog" in lower
            or "jetsam" in lower
        )

    def _extract_duration_ms(self, message: str) -> float | None:
        """Parse hang duration from message text, returning milliseconds."""
        # Try seconds pattern first (e.g., "2.5s", "1.2 seconds")
        match = _DURATION_PATTERNS[0].search(message)
        if match:
            return float(match.group(1)) * 1000

        # Try milliseconds pattern (e.g., "250ms")
        match = _DURATION_PATTERNS[1].search(message)
        if match:
            return float(match.group(1))

        return None

    def _matches_bundle(self, event: dict, bundle_id: str) -> bool:
        """Check if event process name matches the bundle ID."""
        app_name = bundle_id.rsplit(".", maxsplit=1)[-1].lower()
        return app_name in event.get("process", "").lower()

    def _format_event(self, event: dict) -> str:
        """Format a hang event for human-readable terminal output."""
        duration_str = ""
        if "duration_estimate_ms" in event:
            ms = event["duration_estimate_ms"]
            duration_str = f" [{ms / 1000:.1f}s]" if ms >= 1000 else f" [{ms:.0f}ms]"

        return (
            f"HANG {event['timestamp']} | {event['process']} (PID {event['pid']})"
            f"{duration_str} | {event['message'][:120]}"
        )

    def _compute_start_timestamp(self, duration_str: str) -> str:
        """Parse duration string and return ISO-8601 start timestamp."""
        return _compute_start_timestamp(duration_str)

    def _register_signal_handler(self):
        """Register SIGINT handler for graceful shutdown."""

        def handle_sigint(sig, frame):
            self.interrupted = True
            if self._process:
                self._process.terminate()

        signal.signal(signal.SIGINT, handle_sigint)


# === CLI ===


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Watch for iOS simulator hang events via os_log",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/hang_watcher.py --watch --duration 60
  python scripts/hang_watcher.py --watch --bundle-id com.example.app
  python scripts/hang_watcher.py --since 5m --json
  python scripts/hang_watcher.py --watch --duration 30 --predicate '(subsystem == "com.apple.runningboard")'

Environment variables:
  IOS_SIM_HANG_PREDICATE   Override the default log predicate (useful for narrowing/broadening scope)
        """,
    )

    # Mode — mutually exclusive
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--watch",
        action="store_true",
        help="Live stream mode (runs until --duration or Ctrl-C)",
    )
    mode_group.add_argument(
        "--since",
        metavar="DURATION",
        help="Show historical hangs from the past N time units (e.g. 5m, 1h, 30s)",
    )

    # Filters
    parser.add_argument("--bundle-id", help="Filter events to a specific app bundle ID")
    parser.add_argument(
        "--predicate",
        help="Override the default os_log predicate (also settable via IOS_SIM_HANG_PREDICATE)",
    )
    parser.add_argument("--udid", help="Device UDID (uses booted simulator if omitted)")

    # Watch options
    parser.add_argument(
        "--duration",
        type=int,
        metavar="SECONDS",
        help="Stop watching after N seconds (--watch mode only)",
    )

    # Output options
    parser.add_argument("--json", action="store_true", help="Emit JSON lines per hang event")
    parser.add_argument("--verbose", action="store_true", help="Include raw log lines")

    args = parser.parse_args()

    if args.since:
        try:
            _compute_start_timestamp(args.since)  # validate before constructing watcher
        except ValueError as e:
            parser.error(str(e))

    watcher = HangWatcher(udid=args.udid)

    if args.watch:
        success = watcher.watch(
            duration_seconds=args.duration,
            bundle_id=args.bundle_id,
            predicate=args.predicate,
            verbose=args.verbose,
            json_mode=args.json,
        )
    else:
        success = watcher.show_since(
            since_duration=args.since,
            bundle_id=args.bundle_id,
            predicate=args.predicate,
            verbose=args.verbose,
            json_mode=args.json,
        )

    if not success:
        sys.exit(1)

    # Post-run summary (--since mode only — not in live --watch or --json)
    if not args.json and not args.watch:
        print(f"\n{watcher.get_summary()}")

    # Save to cache if events were captured
    if watcher.hang_events:
        cache_id = watcher.save_to_cache()
        print(f"Archive saved: {cache_id}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
