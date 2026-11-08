"""Duo target safety, observed-state verification and capture display routing."""

import json
from unittest.mock import Mock

import pytest

import duo
from common import screenshot_utils
from common.duo_backend import DuoBackend


@pytest.fixture
def manager(monkeypatch):
    """Supply a booted Duo and independent display/sensor readback."""
    device = {"udid": "duo", "state": "Booted", "deviceTypeIdentifier": "SimDeviceType.iPhone-Duo"}
    display = {
        "name": "LCD",
        "active": True,
        "primary": True,
        "displayId": 1,
        "currentOrientation": "rot0",
    }

    def command(args):
        return json.dumps(
            {"devices": {"runtime": [device]}}
            if "simctl" in args
            else {"result": {"displays": [display]}}
        )

    monkeypatch.setattr(duo, "command", command)
    backend = Mock()
    backend.angle.return_value = 0
    return duo.DuoManager("duo", backend)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"angle": 90, "pose": "open"},
        {"angle": -1},
        {"angle": 181},
        {"angle": float("nan")},
        {"angle": float("inf")},
        {"orientation": "bad"},
    ],
)
def test_invalid_request_never_dispatches(manager, kwargs):
    with pytest.raises(ValueError):
        manager.execute(**kwargs)
    manager.backend.assert_not_called()
    manager.backend.angle.assert_not_called()
    manager.backend.hinge.assert_not_called()


def test_wrong_target_never_invokes_helper(manager):
    manager.udid = "other"
    with pytest.raises(ValueError, match="explicit booted"):
        manager.execute()
    manager.backend.angle.assert_not_called()


def test_state_is_observed(manager):
    assert manager.execute() == {
        "success": True,
        "udid": "duo",
        "hinge_angle": 0,
        "active_screen": "cover",
        "display_id": 1,
        "rotation": "rot0",
        "displays": [
            {
                "name": "LCD",
                "active": True,
                "primary": True,
                "displayId": 1,
                "currentOrientation": "rot0",
            }
        ],
    }


def test_hinge_verified_by_readback(manager, monkeypatch):
    manager.backend.angle.side_effect = [90, 0]
    monkeypatch.setattr(duo.time, "sleep", lambda _: None)
    assert manager.execute(pose="closed")["success"]
    manager.backend.hinge.assert_called_once_with("duo", 90, 0)


def test_endpoint_requires_correct_display(manager, monkeypatch):
    manager.backend.angle.return_value = 180
    monkeypatch.setattr(duo.time, "monotonic", Mock(side_effect=[0, 6]))
    result = manager.execute(pose="open")
    assert not result["success"]
    assert result["active_screen"] == "cover"


def test_rotation_requires_observed_orientation(manager, monkeypatch):
    states = [manager.read(), {**manager.read(), "rotation": "rot90"}]
    monkeypatch.setattr(manager, "read", Mock(side_effect=states))
    monkeypatch.setattr(duo.time, "sleep", lambda _: None)
    assert manager.execute(orientation="landscape")["success"]
    manager.backend.orient.assert_called_once_with("duo", "portrait")


def test_readback_failure_is_not_success(manager):
    manager.backend.angle.side_effect = RuntimeError("no sensor")
    with pytest.raises(RuntimeError, match="no sensor"):
        manager.execute(pose="open")
    manager.backend.hinge.assert_not_called()


@pytest.mark.parametrize("value", ["nan", "181", "-1", ""])
def test_native_invalid_angle_rejected(value, monkeypatch):
    backend = DuoBackend()
    monkeypatch.setattr(backend, "invoke", lambda *args: value)
    with pytest.raises(ValueError):
        backend.angle("duo")


@pytest.mark.parametrize("inline", [True, False])
@pytest.mark.parametrize("display", [None, "3"])
def test_capture_routes_display_and_cleans_temp(tmp_path, monkeypatch, inline, display):
    commands = []

    def run(args, **kwargs):
        commands.append(args)
        from pathlib import Path

        Path(args[-1]).write_bytes(b"png")

    monkeypatch.setattr(screenshot_utils.subprocess, "run", run)
    monkeypatch.setattr(screenshot_utils, "HAS_PIL", False)
    result = screenshot_utils.capture_screenshot(
        "duo", str(tmp_path / "out.png"), inline=inline, display=display
    )
    assert ("--display=3" in commands[0]) == (display is not None)
    assert result.get("display_id") == display
    assert result["width"] == result["height"] == 0
    from pathlib import Path

    assert not Path(commands[0][-1]).exists()
