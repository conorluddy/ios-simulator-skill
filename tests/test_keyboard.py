"""Unit tests for keyboard.py: key codes, Cmd+A clear, hardware button names."""

import keyboard
import pytest
from keyboard import HARDWARE_BUTTONS, KeyboardController, resolve_key_code

# idb's HIDButtonType names (idb/common/types.py)
IDB_BUTTON_NAMES = {
    "APPLE_PAY",
    "HOME",
    "LOCK",
    "SIDE_BUTTON",
    "SIRI",
    "PLAY_PAUSE",
    "VOLUME_UP",
    "VOLUME_DOWN",
    "EJECT",
}


@pytest.fixture
def idb_calls(monkeypatch):
    """Capture idb commands; every call succeeds."""
    calls: list[list[str]] = []

    def fake_run(cmd):
        calls.append(cmd)
        return (True, "")

    monkeypatch.setattr(keyboard, "run_idb", fake_run)
    monkeypatch.setattr(keyboard.time, "sleep", lambda seconds: None)
    return calls


@pytest.mark.parametrize(
    ("key", "code"),
    [("return", 40), ("DELETE", 42), ("a", 4), ("h", 11), ("z", 29), ("42", 42)],
)
def test_resolve_key_code(key, code):
    assert resolve_key_code(key) == code


def test_unknown_key_is_rejected():
    assert resolve_key_code("command") is None


def test_clear_selects_all_with_command_a_then_deletes(idb_calls):
    assert KeyboardController("U").clear_text()
    assert idb_calls == [
        ["idb", "ui", "key", "4", "--command", "--udid", "U"],
        ["idb", "ui", "key", "42", "--udid", "U"],
    ]


def test_key_sequence_accepts_letters(idb_calls):
    assert KeyboardController("U").press_key_sequence(["h", "i", "return"])
    assert idb_calls == [["idb", "ui", "key-sequence", "11", "12", "40", "--udid", "U"]]


def test_key_sequence_names_the_bad_key(idb_calls):
    controller = KeyboardController("U")
    assert not controller.press_key_sequence(["h", "cmd"])
    assert "'cmd'" in controller.last_error
    assert idb_calls == []


def test_every_button_maps_to_a_real_idb_button():
    assert set(HARDWARE_BUTTONS.values()) <= IDB_BUTTON_NAMES


def test_home_button(idb_calls):
    assert KeyboardController("U").press_hardware_button("home")
    assert idb_calls == [["idb", "ui", "button", "HOME", "--udid", "U"]]


def test_unknown_button_fails_with_choices(idb_calls):
    controller = KeyboardController("U")
    assert not controller.press_hardware_button("ringer")
    assert "choose from" in controller.last_error


def test_volume_failure_hints_at_idb_upgrade(monkeypatch):
    monkeypatch.setattr(keyboard, "run_idb", lambda cmd: (False, "invalid choice: 'VOLUME_UP'"))
    controller = KeyboardController("U")
    assert not controller.press_hardware_button("volume-up")
    assert "idb 1.6.3+" in controller.last_error
