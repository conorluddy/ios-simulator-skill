"""Unit tests for media.py: simctl addmedia for adding, idb photos clear for clearing."""

import subprocess
from types import SimpleNamespace

import media
import pytest
from media import MediaManager

UDID = "UDID-1"


@pytest.fixture
def photo_files(tmp_path):
    """Two real files so the existence guard passes."""
    paths = [tmp_path / "a.png", tmp_path / "b.jpg"]
    for path in paths:
        path.write_bytes(b"x")
    return [str(path) for path in paths]


@pytest.fixture
def commands(monkeypatch):
    """Capture simctl (subprocess.run) and idb (run_idb) commands; all succeed."""
    calls: list[list[str]] = []

    def fake_subprocess_run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(stdout="", stderr="")

    def fake_run_idb(cmd):
        calls.append(cmd)
        return (True, "")

    monkeypatch.setattr(media.subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(media, "run_idb", fake_run_idb)
    return calls


def test_add_uses_simctl_addmedia_with_all_files(commands, photo_files):
    ok, message = MediaManager(UDID).add(photo_files)
    assert ok
    assert message == "Added 2 file(s) to photo library"
    assert commands == [["xcrun", "simctl", "addmedia", UDID, *photo_files]]


def test_add_rejects_missing_file_without_running_simctl(commands, photo_files):
    ok, message = MediaManager(UDID).add([photo_files[0], "/nope/missing.png"])
    assert not ok
    assert "/nope/missing.png" in message
    assert commands == []


def test_add_surfaces_simctl_stderr(monkeypatch, photo_files):
    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr="Unsupported format\n")

    monkeypatch.setattr(media.subprocess, "run", fake_run)
    assert MediaManager(UDID).add(photo_files) == (False, "Unsupported format")


def test_clear_uses_idb_photos_clear(commands):
    assert MediaManager(UDID).clear() == (True, "Photo library cleared")
    assert commands == [["idb", "photos", "clear", "--udid", UDID]]


def test_clear_adds_upgrade_hint_on_pre_1_7_idb(monkeypatch):
    stderr = "idb: error: argument command: invalid choice: 'photos'"
    monkeypatch.setattr(media, "run_idb", lambda cmd: (False, stderr))
    ok, error = MediaManager(UDID).clear()
    assert not ok
    assert stderr in error
    assert "needs idb 1.7+" in error and "\n" not in error


def test_clear_passes_other_idb_errors_through_without_hint(monkeypatch):
    monkeypatch.setattr(media, "run_idb", lambda cmd: (False, "companion not running"))
    assert MediaManager(UDID).clear() == (False, "companion not running")


# === --clear confirmation (AGENTS.md Principle 10) ===


def test_clear_with_photos_refuses_without_yes(monkeypatch):
    manager = MediaManager(udid=UDID)
    monkeypatch.setattr(manager, "photo_count", lambda: 14)
    refusal = media.clear_refusal(manager, is_confirmed=False)
    assert refusal.startswith(f"Refusing to delete 14 photo(s) on {UDID} without --yes")
    assert "\n" not in refusal


def test_clear_of_an_empty_library_needs_no_confirmation(monkeypatch):
    manager = MediaManager(udid=UDID)
    monkeypatch.setattr(manager, "photo_count", lambda: 0)
    assert media.clear_refusal(manager, is_confirmed=False) is None


def test_clear_proceeds_with_yes(monkeypatch):
    manager = MediaManager(udid=UDID)
    monkeypatch.setattr(manager, "photo_count", lambda: 14)
    assert media.clear_refusal(manager, is_confirmed=True) is None


def test_unknown_photo_count_still_refuses(monkeypatch):
    manager = MediaManager(udid=UDID)
    monkeypatch.setattr(manager, "photo_count", lambda: None)
    assert "delete the photo library" in media.clear_refusal(manager, is_confirmed=False)


def test_photo_count_reads_the_simulator_library(monkeypatch, tmp_path):
    dcim = tmp_path / UDID / "data/Media/DCIM/100APPLE"
    dcim.mkdir(parents=True)
    for name in ("IMG_1.JPG", "IMG_2.heic", "notes.txt"):
        (dcim / name).write_bytes(b"x")
    monkeypatch.setattr(media, "SIMULATOR_DEVICES_DIR", tmp_path)
    assert MediaManager(udid=UDID).photo_count() == 2
