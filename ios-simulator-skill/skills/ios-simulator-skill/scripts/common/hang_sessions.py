#!/usr/bin/env python3
"""HangBuster session storage — own dir layout, no ProgressiveCache reuse.

Each session is a directory under ``~/.ios-simulator-skill/sessions/<id>/``
containing ``meta.json`` (config + pid + status), ``events.jsonl``
(append-only normalised events), and ``summary.json`` (post-stop).

The parent creates the directory and writes initial meta. The detached
worker updates meta with its own pid (avoids pidfile race) and appends to
events.jsonl. ``--stop`` SIGTERMs the worker, drains events, builds a
``SessionSummary``, and writes ``summary.json``.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import secrets
import signal
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from common.env_config import env_int
from common.hang_pipeline import (
    SessionSummary,
    SummaryBuilder,
    event_from_jsonl,
    summary_from_json,
    summary_to_json,
)

# === CONSTANTS ===

DEFAULT_SESSIONS_DIR = Path("~/.ios-simulator-skill/sessions").expanduser()
DEFAULT_TTL_HOURS = env_int("IOS_SIM_HANG_SESSION_TTL_HOURS", 24)

_STATUS_PENDING = "pending"
_STATUS_RUNNING = "running"
_STATUS_STOPPED = "stopped"
_STATUS_CRASHED = "crashed"

_DURATION_RE = re.compile(r"(\d+)([smhd])$")


# === TYPES ===


@dataclass
class SessionMeta:
    """Parent + worker writes to meta.json."""

    session_id: str
    started_at: str
    started_at_ms: int
    args: dict
    pid: int | None = None
    status: str = _STATUS_PENDING
    stopped_at: str | None = None
    stopped_at_ms: int | None = None
    extras: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "started_at_ms": self.started_at_ms,
            "args": self.args,
            "pid": self.pid,
            "status": self.status,
            "stopped_at": self.stopped_at,
            "stopped_at_ms": self.stopped_at_ms,
            "extras": self.extras,
        }

    @classmethod
    def from_json(cls, payload: dict) -> SessionMeta:
        return cls(
            session_id=payload["session_id"],
            started_at=payload["started_at"],
            started_at_ms=payload["started_at_ms"],
            args=payload.get("args", {}),
            pid=payload.get("pid"),
            status=payload.get("status", _STATUS_PENDING),
            stopped_at=payload.get("stopped_at"),
            stopped_at_ms=payload.get("stopped_at_ms"),
            extras=payload.get("extras", {}),
        )


# === SESSION STORE ===


class SessionStore:
    """Filesystem-backed session repository."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = Path(base_dir).expanduser() if base_dir else DEFAULT_SESSIONS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # === PUBLIC API ===

    def create(self, args: dict) -> SessionMeta:
        """Generate id + dir + initial meta.json. Caller detaches the worker next."""
        session_id = _generate_session_id()
        session_dir = self.base_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=False)
        # Empty events file so the worker can `open(..., 'a')` cleanly.
        (session_dir / "events.jsonl").touch()
        now = datetime.now()
        meta = SessionMeta(
            session_id=session_id,
            started_at=now.isoformat(),
            started_at_ms=int(now.timestamp() * 1000),
            args=args,
            status=_STATUS_PENDING,
        )
        self._write_meta(meta)
        return meta

    def wait_for_worker(self, session_id: str, timeout_seconds: float = 2.0) -> SessionMeta:
        """Poll meta.json until status=running or timeout. Raises on timeout."""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            meta = self.load_meta(session_id)
            if meta.status == _STATUS_RUNNING and meta.pid:
                return meta
            time.sleep(0.05)
        raise TimeoutError(f"Worker for {session_id} did not register within {timeout_seconds}s")

    def claim_worker(self, session_id: str, pid: int) -> SessionMeta:
        """Called by worker on startup. Writes pid + status=running into meta."""
        meta = self.load_meta(session_id)
        meta.pid = pid
        meta.status = _STATUS_RUNNING
        self._write_meta(meta)
        return meta

    def persist_worker_counters(self, session_id: str, counters: dict) -> None:
        """Worker calls this at shutdown to flush its line counters into meta.

        Re-reads meta from disk so a concurrent ``stop()`` that already wrote
        ``status=stopped`` is not clobbered back to ``running``.
        """
        meta = self.load_meta(session_id)
        meta.extras["line_counters"] = counters
        if meta.status != _STATUS_STOPPED:
            meta.status = _STATUS_RUNNING
        self._write_meta(meta)

    def stop(self, session_id: str, summary: SessionSummary) -> SessionMeta:
        """Mark session stopped and persist the computed summary."""
        meta = self.load_meta(session_id)
        meta.status = _STATUS_STOPPED
        now = datetime.now()
        meta.stopped_at = now.isoformat()
        meta.stopped_at_ms = int(now.timestamp() * 1000)
        self._write_meta(meta)
        self._write_summary(session_id, summary)
        return meta

    def mark_crashed(self, session_id: str) -> None:
        """Best-effort: tag a session whose worker exited without a summary."""
        try:
            meta = self.load_meta(session_id)
        except FileNotFoundError:
            return
        meta.status = _STATUS_CRASHED
        self._write_meta(meta)

    def signal_worker(self, session_id: str, sig: int = signal.SIGTERM) -> bool:
        """Send ``sig`` to the worker pid recorded in meta.json. Returns True if delivered."""
        meta = self.load_meta(session_id)
        if not meta.pid:
            return False
        try:
            os.kill(meta.pid, sig)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return False

    def load_meta(self, session_id: str) -> SessionMeta:
        path = self._meta_path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"No meta.json for session {session_id}")
        with open(path) as handle:
            return SessionMeta.from_json(json.load(handle))

    def load_summary(self, session_id: str) -> SessionSummary | None:
        path = self._summary_path(session_id)
        if not path.exists():
            return None
        with open(path) as handle:
            return summary_from_json(json.load(handle))

    def read_events(self, session_id: str) -> list:
        """Read all events.jsonl lines, returning NormalisedEvent instances.

        Skips non-event sentinel lines (e.g. ``{"event": "stream_ended"}``).
        """
        path = self._events_path(session_id)
        if not path.exists():
            return []
        events = []
        with open(path) as handle:
            for raw in handle:
                line = raw.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Skip non-event sentinel lines (e.g. {"event": "stream_ended"}).
                if payload.get("event") == "stream_ended":
                    continue
                try:
                    events.append(event_from_jsonl(line))
                except (json.JSONDecodeError, KeyError):
                    continue
        return events

    def events_path(self, session_id: str) -> Path:
        """Worker writes here. Public so the worker can open it line-buffered."""
        return self._events_path(session_id)

    def session_dir(self, session_id: str) -> Path:
        return self.base_dir / session_id

    def list_sessions(self) -> list[SessionMeta]:
        """All non-expired session metas, newest first."""
        metas: list[SessionMeta] = []
        for entry in self.base_dir.iterdir():
            if not entry.is_dir():
                continue
            try:
                metas.append(self.load_meta(entry.name))
            except (FileNotFoundError, json.JSONDecodeError):
                continue
        metas.sort(key=lambda m: m.started_at_ms, reverse=True)
        return metas

    def clear(self, older_than: str | None = None) -> int:
        """Delete session dirs. ``older_than`` is a duration string like ``24h``."""
        cutoff_ms = _resolve_cutoff_ms(older_than) if older_than else None
        deleted = 0
        for entry in self.base_dir.iterdir():
            if not entry.is_dir():
                continue
            try:
                meta = self.load_meta(entry.name)
            except (FileNotFoundError, json.JSONDecodeError):
                _remove_tree(entry)
                deleted += 1
                continue
            if cutoff_ms is None or meta.started_at_ms <= cutoff_ms:
                _remove_tree(entry)
                deleted += 1
        return deleted

    def prune_expired(self, ttl_hours: int | None = None) -> int:
        """Remove sessions older than ttl. Called on every ``create``."""
        ttl = ttl_hours if ttl_hours is not None else DEFAULT_TTL_HOURS
        cutoff = int((datetime.now() - timedelta(hours=ttl)).timestamp() * 1000)
        return self._clear_older_than_ms(cutoff)

    # === SUMMARY HELPERS ===

    def build_summary(
        self,
        session_id: str,
        matched_lines: int = 0,
        total_lines: int = 0,
        dropped_below_threshold: int = 0,
        extras: dict | None = None,
        top_n: int | None = None,
    ) -> SessionSummary:
        """Convenience: read events.jsonl and run the pipeline through SummaryBuilder."""
        meta = self.load_meta(session_id)
        events = self.read_events(session_id)
        now = datetime.now()
        duration_ms = int(now.timestamp() * 1000) - meta.started_at_ms
        builder = SummaryBuilder(
            session_id=session_id,
            started_at=meta.started_at,
            duration_ms=max(0, duration_ms),
            matched_lines=matched_lines,
            total_lines=total_lines,
            dropped_below_threshold=dropped_below_threshold,
            extras=extras or {},
        )
        return builder.build(events, top_n=top_n)

    # === PRIVATE ===

    def _meta_path(self, session_id: str) -> Path:
        return self.base_dir / session_id / "meta.json"

    def _events_path(self, session_id: str) -> Path:
        return self.base_dir / session_id / "events.jsonl"

    def _summary_path(self, session_id: str) -> Path:
        return self.base_dir / session_id / "summary.json"

    def _write_meta(self, meta: SessionMeta) -> None:
        path = self._meta_path(meta.session_id)
        tmp = path.with_suffix(".json.tmp")
        # Atomic write — concurrent reads (e.g. the parent polling) never see a half-file.
        # fsync before replace makes the new contents durable, not just atomically renamed.
        with open(tmp, "w") as handle:
            json.dump(meta.to_json(), handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        tmp.replace(path)

    def _write_summary(self, session_id: str, summary: SessionSummary) -> None:
        path = self._summary_path(session_id)
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w") as handle:
            json.dump(summary_to_json(summary), handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        tmp.replace(path)

    def _clear_older_than_ms(self, cutoff_ms: int) -> int:
        deleted = 0
        for entry in self.base_dir.iterdir():
            if not entry.is_dir():
                continue
            try:
                meta = self.load_meta(entry.name)
            except (FileNotFoundError, json.JSONDecodeError):
                _remove_tree(entry)
                deleted += 1
                continue
            if meta.started_at_ms <= cutoff_ms:
                _remove_tree(entry)
                deleted += 1
        return deleted


# === MODULE-LEVEL HELPERS ===


def _generate_session_id() -> str:
    """``hang-YYYYMMDD-HHmmss-XXXX`` — random hex suffix avoids same-second collisions."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = secrets.token_hex(2)
    return f"hang-{timestamp}-{suffix}"


def _resolve_cutoff_ms(duration_str: str) -> int:
    """Parse e.g. ``24h``, ``30m`` and return the epoch-ms threshold."""
    match = _DURATION_RE.match(duration_str.strip().lower())
    if not match:
        raise ValueError(f"Invalid duration: {duration_str!r}. Use 30s/5m/24h/7d.")
    value, unit = int(match.group(1)), match.group(2)
    seconds = value * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    cutoff = datetime.now() - timedelta(seconds=seconds)
    return int(cutoff.timestamp() * 1000)


def _remove_tree(path: Path) -> None:
    """rm -rf path. Used for session-dir cleanup."""
    for child in path.iterdir():
        if child.is_dir():
            _remove_tree(child)
        else:
            with contextlib.suppress(FileNotFoundError):
                child.unlink()
    with contextlib.suppress(OSError):
        path.rmdir()
