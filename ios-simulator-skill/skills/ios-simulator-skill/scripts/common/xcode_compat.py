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

Backward compatible by construction: on any Xcode where SimulatorKit already
lives at the legacy path, the existence check at the top short-circuits and
DEVELOPER_DIR is left untouched.
"""

import os
import shutil
import subprocess
from pathlib import Path

SHIM_ROOT = Path.home() / ".ios-simulator-skill" / "xcode27-idb-shim"
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
