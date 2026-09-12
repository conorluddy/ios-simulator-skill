"""
Xcode 27+ compatibility shim for idb-companion.

Xcode 27 moved `SimulatorKit.framework` from
`Contents/Developer/Library/PrivateFrameworks/` to `Contents/SharedFrameworks/`.
idb-companion <= 1.1.8 still hardcodes the old path and refuses to launch
("SimulatorKit is required for HID interactions") under the new layout,
which breaks every `idb ui *` call (navigator.py, gesture.py, keyboard.py).

`ensure_idb_companion_developer_dir()` builds a persistent DEVELOPER_DIR shim
under `~/.ios-simulator-skill/` - a directory tree of symlinks back into the
real Xcode.app, plus one extra symlink exposing SimulatorKit at the path
idb-companion expects - and points DEVELOPER_DIR at it for the current
process (inherited by every `idb`/`idb_companion` subprocess it spawns).

The shim root MUST be named `*.app`: `xcrun` walks up from DEVELOPER_DIR
looking for an enclosing app bundle and refuses a developer dir without one
("unable to find Xcode installation from active developer path"). Since
DEVELOPER_DIR is process-wide, a non-.app shim root breaks every `xcrun
simctl` call in the same script - screenshots, boot, io - not just idb.

Backward compatible by construction: on any Xcode where SimulatorKit already
lives at the legacy path, the existence check at the top short-circuits and
DEVELOPER_DIR is left untouched.
"""

import contextlib
import json
import os
import shutil
import signal
import subprocess
from pathlib import Path

SHIM_ROOT = Path.home() / ".ios-simulator-skill" / "Xcode27Shim.app"
LEGACY_SHIM_ROOT = Path.home() / ".ios-simulator-skill" / "xcode27-idb-shim"
LEGACY_SIMULATOR_KIT = Path("Library/PrivateFrameworks/SimulatorKit.framework")
SIBLINGS_TO_LINK = ("Info.plist", "SharedFrameworks", "PlugIns", "Resources")


def ensure_idb_companion_developer_dir() -> None:
    """Point DEVELOPER_DIR at a shim if this Xcode has the Xcode 27+ layout.

    Safe to call on every script invocation: cheap existence checks up front,
    a no-op once the shim exists, and a no-op entirely on any Xcode that
    already has SimulatorKit at the legacy path. Never raises - a shim
    failure should degrade to idb's normal (pre-existing) error, not crash
    the calling script.
    """
    if os.environ.get("IOS_SIM_SKIP_XCODE27_SHIM"):
        return

    try:
        developer_dir = _developer_dir()
        if developer_dir is None or (developer_dir / LEGACY_SIMULATOR_KIT).exists():
            return  # no Xcode found, or legacy layout already has it

        shared_simulator_kit = developer_dir.parent / "SharedFrameworks" / "SimulatorKit.framework"
        if not shared_simulator_kit.exists():
            return  # neither layout has it - not ours to fix, let idb fail normally

        shim_developer_dir = SHIM_ROOT / "Contents" / "Developer"
        shim_simulator_kit = shim_developer_dir / LEGACY_SIMULATOR_KIT

        if not _shim_points_at(shim_simulator_kit, shared_simulator_kit):
            _build_shim(developer_dir, shim_developer_dir, shared_simulator_kit)

        os.environ["DEVELOPER_DIR"] = str(shim_developer_dir)
        _retire_stale_companions(shim_developer_dir)
        _remove_legacy_shim()
    except Exception as error:
        print(f"Note: Xcode 27 idb-companion shim skipped ({error})", file=__import__("sys").stderr)


def _developer_dir() -> Path | None:
    try:
        result = subprocess.run(
            ["xcode-select", "-p"], capture_output=True, text=True, check=True, timeout=5
        )
        path = Path(result.stdout.strip())
        return path if path.exists() else None
    except Exception:
        return None


def _shim_points_at(symlink_path: Path, target: Path) -> bool:
    try:
        return symlink_path.is_symlink() and symlink_path.resolve() == target.resolve()
    except OSError:
        return False


def _build_shim(
    real_developer_dir: Path, shim_developer_dir: Path, shared_simulator_kit: Path
) -> None:
    xcode_contents = real_developer_dir.parent  # .../Xcode.app/Contents
    shim_contents = shim_developer_dir.parent

    if shim_contents.exists():
        shutil.rmtree(shim_contents)

    shim_developer_dir.mkdir(parents=True)
    (shim_developer_dir / "Library" / "PrivateFrameworks").mkdir(parents=True)

    for child in real_developer_dir.iterdir():
        if child.name != "Library":
            (shim_developer_dir / child.name).symlink_to(child)

    for child in (real_developer_dir / "Library").iterdir():
        (shim_developer_dir / "Library" / child.name).symlink_to(child)

    (shim_developer_dir / LEGACY_SIMULATOR_KIT).symlink_to(shared_simulator_kit)

    for sibling in SIBLINGS_TO_LINK:
        target = xcode_contents / sibling
        if target.exists():
            (shim_contents / sibling).symlink_to(target)


def _retire_stale_companions(shim_developer_dir: Path) -> None:
    """Kill any idb-companion still running outside the shim.

    A companion inherits DEVELOPER_DIR once, at launch. One started before the
    shim existed keeps the broken SimulatorKit path for its whole lifetime -
    reconnecting does not help, because `idb connect` reuses the live process
    and its socket. Killing it here lets the next `idb` call spawn a fresh
    companion under the shimmed environment.

    Killing the process is not enough on its own: idb's registry at
    `/tmp/idb/state` still lists the dead pid and its socket, and idb will
    dial that socket and fail ("Connection refused") rather than spawn a
    replacement. So each retired companion is evicted from the registry and
    its socket unlinked.
    """
    retired_pids = {
        pid
        for pid in _running_companion_pids()
        if _companion_developer_dir(pid) != str(shim_developer_dir)
    }
    for pid in retired_pids:
        _terminate(pid)
    if retired_pids:
        _evict_from_idb_registry(retired_pids)


def _running_companion_pids() -> list[int]:
    try:
        result = subprocess.run(
            ["pgrep", "-f", "idb_companion"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return []
    return [int(line) for line in result.stdout.split() if line.isdigit()]


def _companion_developer_dir(pid: int) -> str | None:
    """Read DEVELOPER_DIR out of a running companion's environment, or None."""
    try:
        result = subprocess.run(
            ["ps", "eww", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return None
    for token in result.stdout.split():
        if token.startswith("DEVELOPER_DIR="):
            return token.removeprefix("DEVELOPER_DIR=")
    return None


def _terminate(pid: int) -> None:
    # Already gone, or not ours to kill - either way the next idb call will tell us.
    with contextlib.suppress(OSError):
        os.kill(pid, signal.SIGTERM)


def _remove_legacy_shim() -> None:
    """Delete the pre-.app shim root left by earlier versions (see module docstring)."""
    # A leftover shim costs disk, not correctness.
    with contextlib.suppress(OSError):
        if LEGACY_SHIM_ROOT.is_dir():
            shutil.rmtree(LEGACY_SHIM_ROOT)


def _evict_from_idb_registry(retired_pids: set[int]) -> None:
    """Drop retired companions from idb's registry and unlink their sockets.

    A registry entry pointing at a dead companion makes idb fail the next call
    instead of spawning a working one - the trap behind "reconnecting doesn't
    help" on Xcode 27.
    """
    registry_path = Path("/tmp/idb/state")
    try:
        entries = json.loads(registry_path.read_text())
    except (OSError, json.JSONDecodeError):
        return  # no registry yet, or idb changed its format - leave it alone

    surviving = [entry for entry in entries if entry.get("pid") not in retired_pids]
    if len(surviving) == len(entries):
        return

    for entry in entries:
        if entry.get("pid") in retired_pids and entry.get("path"):
            with contextlib.suppress(OSError):
                Path(entry["path"]).unlink()

    with contextlib.suppress(OSError):
        registry_path.write_text(json.dumps(surviving))
