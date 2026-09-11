"""Xcode 27+ moved SimulatorKit.framework; idb-companion still expects the old path."""

from pathlib import Path
from unittest.mock import patch

from common.xcode_compat import ensure_idb_companion_developer_dir


def _make_xcode(
    tmp_path: Path, *, shared_frameworks: bool, legacy_private_frameworks: bool
) -> Path:
    """Build a fake Xcode.app skeleton with just enough to exercise the shim."""
    contents = tmp_path / "Xcode.app" / "Contents"
    developer = contents / "Developer"
    (developer / "Library").mkdir(parents=True)
    (developer / "Toolchains").mkdir()

    if legacy_private_frameworks:
        (developer / "Library" / "PrivateFrameworks").mkdir()
        (developer / "Library" / "PrivateFrameworks" / "SimulatorKit.framework").mkdir()

    if shared_frameworks:
        (contents / "SharedFrameworks" / "SimulatorKit.framework").mkdir(parents=True)

    (contents / "Info.plist").write_text("<plist/>")
    return developer


class TestEnsureIdbCompanionDeveloperDir:
    def test_legacy_xcode_layout_is_untouched(self, tmp_path, monkeypatch):
        """Old Xcode with SimulatorKit already at the expected path: no shim, no env change."""
        developer = _make_xcode(tmp_path, shared_frameworks=False, legacy_private_frameworks=True)
        monkeypatch.delenv("DEVELOPER_DIR", raising=False)
        with patch("common.xcode_compat._developer_dir", return_value=developer):
            ensure_idb_companion_developer_dir()
        assert "DEVELOPER_DIR" not in __import__("os").environ

    def test_xcode27_layout_builds_shim_and_sets_developer_dir(self, tmp_path, monkeypatch):
        """New Xcode 27 layout (SimulatorKit under SharedFrameworks): shim built, env points at it."""
        developer = _make_xcode(tmp_path, shared_frameworks=True, legacy_private_frameworks=False)
        shim_root = tmp_path / "shim-home"
        monkeypatch.delenv("DEVELOPER_DIR", raising=False)
        with (
            patch("common.xcode_compat._developer_dir", return_value=developer),
            patch("common.xcode_compat.SHIM_ROOT", shim_root),
        ):
            ensure_idb_companion_developer_dir()

        shimmed_developer_dir = Path(__import__("os").environ["DEVELOPER_DIR"])
        assert shimmed_developer_dir == shim_root / "Contents" / "Developer"

        shimmed_simulator_kit = (
            shimmed_developer_dir / "Library" / "PrivateFrameworks" / "SimulatorKit.framework"
        )
        assert (
            shimmed_simulator_kit.resolve()
            == (developer.parent / "SharedFrameworks" / "SimulatorKit.framework").resolve()
        )

    def test_neither_layout_present_leaves_developer_dir_alone(self, tmp_path, monkeypatch):
        """Xcode with SimulatorKit in neither location: not our bug to fix, don't touch env."""
        developer = _make_xcode(tmp_path, shared_frameworks=False, legacy_private_frameworks=False)
        monkeypatch.delenv("DEVELOPER_DIR", raising=False)
        with patch("common.xcode_compat._developer_dir", return_value=developer):
            ensure_idb_companion_developer_dir()
        assert "DEVELOPER_DIR" not in __import__("os").environ

    def test_opt_out_env_var_skips_entirely(self, tmp_path, monkeypatch):
        developer = _make_xcode(tmp_path, shared_frameworks=True, legacy_private_frameworks=False)
        monkeypatch.setenv("IOS_SIM_SKIP_XCODE27_SHIM", "1")
        monkeypatch.delenv("DEVELOPER_DIR", raising=False)
        with patch("common.xcode_compat._developer_dir", return_value=developer):
            ensure_idb_companion_developer_dir()
        assert "DEVELOPER_DIR" not in __import__("os").environ

    def test_rerun_reuses_existing_shim_without_rebuilding(self, tmp_path, monkeypatch):
        """Calling twice (e.g. two scripts in one session) must not rebuild an already-correct shim."""
        developer = _make_xcode(tmp_path, shared_frameworks=True, legacy_private_frameworks=False)
        shim_root = tmp_path / "shim-home"
        monkeypatch.delenv("DEVELOPER_DIR", raising=False)
        with (
            patch("common.xcode_compat._developer_dir", return_value=developer),
            patch("common.xcode_compat.SHIM_ROOT", shim_root),
            patch(
                "common.xcode_compat._build_shim",
                wraps=__import__("common.xcode_compat", fromlist=["_build_shim"])._build_shim,
            ) as build_shim,
        ):
            ensure_idb_companion_developer_dir()
            ensure_idb_companion_developer_dir()

        assert build_shim.call_count == 1
