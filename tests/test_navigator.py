"""Unit tests for navigator.py: exact matching, match ranking, failure reasons."""

import navigator
import pytest
from navigator import Navigator


def _node(node_type, label, x, y, width, height, children=()):
    return {
        "type": node_type,
        "AXLabel": label,
        "frame": {"x": x, "y": y, "width": width, "height": height},
        "enabled": True,
        "children": list(children),
    }


SETTINGS_TREE = _node(
    "Application",
    "Settings",
    0,
    0,
    400,
    800,
    [
        _node("Group", "Settings", 0, 0, 400, 100),
        _node("Button", "Settings", 20, 20, 80, 40),
        _node("Button", "General Settings", 20, 200, 300, 44),
    ],
)


@pytest.fixture
def nav(monkeypatch):
    """Navigator over SETTINGS_TREE, capturing idb commands."""
    calls: list[list[str]] = []

    def fake_run(cmd):
        calls.append(cmd)
        return (True, "")

    monkeypatch.setattr(navigator, "get_accessibility_tree", lambda udid, nested: SETTINGS_TREE)
    monkeypatch.setattr(navigator, "run_idb", fake_run)
    instance = Navigator("U")
    instance.calls = calls
    return instance


def test_button_beats_containers_with_same_label(nav):
    element = nav.find_element(text="Settings")
    assert element.type == "Button"
    assert element.label == "Settings"


def test_exact_tap_ignores_partial_matches(nav):
    ok, message = nav.find_and_tap(text="General", fuzzy=False)
    assert not ok
    assert "Not found" in message
    assert nav.calls == []


def test_exact_tap_hits_the_exact_label(nav):
    ok, _ = nav.find_and_tap(text="General Settings", fuzzy=False)
    assert ok
    assert nav.calls == [["idb", "ui", "tap", "170", "222", "--udid", "U"]]


def test_failed_tap_reports_idb_reason(nav, monkeypatch):
    monkeypatch.setattr(navigator, "run_idb", lambda cmd: (False, "Connection refused"))
    ok, message = nav.find_and_tap(text="Settings")
    assert not ok
    assert "Connection refused" in message


def test_exact_match_ranks_first_regardless_of_case():
    partial = navigator.Element("Button", "General Settings", None, None, {}, [])
    exact = navigator.Element("Button", "Settings", None, None, {}, [])
    assert navigator.rank_match(exact, "settings") < navigator.rank_match(partial, "settings")


def test_type_only_search_keeps_screen_order(monkeypatch):
    form = _node(
        "Application",
        "Login",
        0,
        0,
        400,
        800,
        [
            _node("TextField", "Email", 20, 100, 360, 44),
            _node("TextField", "Password", 20, 160, 300, 44),
        ],
    )
    monkeypatch.setattr(navigator, "get_accessibility_tree", lambda udid, nested: form)
    nav = Navigator("U")
    assert nav.find_element(element_type="TextField").label == "Email"
    assert nav.find_element(element_type="TextField", index=1).label == "Password"


# === Accessibility press and set-value (idb 1.7) ===


def _with_id(node, identifier):
    node["AXUniqueId"] = identifier
    return node


OVERLAY_TREE = _node(
    "Application",
    "Settings",
    0,
    0,
    400,
    800,
    [
        _with_id(_node("Button", "Screen Time", 16, 796, 370, 52), "settings.screenTime"),
        _with_id(
            _node("Button", "Screen Time Limits", 16, 600, 370, 52), "settings.screenTimeLimits"
        ),
        _with_id(_node("Button", "General", 16, 300, 370, 52), "settings.general"),
        _with_id(_node("TextField", "Search", 28, 808, 346, 28), "searchField"),
    ],
)


@pytest.fixture
def press_nav(monkeypatch):
    """Navigator over OVERLAY_TREE on an idb with set-value."""
    calls: list[list[str]] = []

    def fake_run(cmd):
        calls.append(cmd)
        return (True, "")

    monkeypatch.setattr(navigator, "get_accessibility_tree", lambda udid, nested: OVERLAY_TREE)
    monkeypatch.setattr(navigator, "run_idb", fake_run)
    monkeypatch.setattr(navigator, "idb_supports_set_value", lambda: True)
    instance = Navigator("U")
    instance.calls = calls
    return instance


MARKER_ARGS = ["--match-key", "AXUniqueId", "--api", "ax"]


def test_uniquely_identified_button_is_pressed_not_tapped(press_nav):
    ok, message = press_nav.find_and_tap(text="General", fuzzy=False)
    assert ok
    assert "accessibility press" in message
    assert press_nav.calls == [
        ["idb", "ui", "tap", "settings.general", *MARKER_ARGS, "--udid", "U"]
    ]


def test_identifier_contained_in_another_falls_back_to_coordinates(press_nav):
    # idb would match "settings.screenTime" against "settings.screenTimeLimits" too.
    ok, message = press_nav.find_and_tap(text="Screen Time", fuzzy=False)
    assert ok
    assert press_nav.calls == [["idb", "ui", "tap", "201", "822", "--udid", "U"]]
    assert "at (201, 822)" in message


def test_failed_press_falls_back_to_coordinate_tap(press_nav, monkeypatch):
    results = iter([(False, "no element"), (True, "")])
    monkeypatch.setattr(
        navigator, "run_idb", lambda cmd: press_nav.calls.append(cmd) or next(results)
    )
    ok, message = press_nav.find_and_tap(text="General", fuzzy=False)
    assert ok
    assert press_nav.calls[-1] == ["idb", "ui", "tap", "201", "326", "--udid", "U"]
    assert "at (201, 326)" in message


def test_enter_text_taps_field_coordinates_for_keyboard_focus(press_nav, monkeypatch):
    monkeypatch.setattr(navigator, "TAP_SETTLE_SECONDS", 0)
    ok, _ = press_nav.find_and_enter_text("hello", identifier="searchField")
    assert ok
    assert press_nav.calls[0] == ["idb", "ui", "tap", "201", "822", "--udid", "U"]


def test_set_value_addresses_field_by_unique_identifier(press_nav):
    ok, message = press_nav.find_and_enter_text("Zürich", identifier="searchField", replace=True)
    assert ok
    assert message == 'Set value of: TextField "Search"'
    assert press_nav.calls == [
        ["idb", "ui", "set-value", "searchField", *MARKER_ARGS, "--value", "Zürich", "--udid", "U"]
    ]


def test_set_value_without_identifier_uses_coordinates(nav, monkeypatch):
    monkeypatch.setattr(navigator, "idb_supports_set_value", lambda: True)
    ok, _ = nav.find_and_enter_text("x", find_text="General", element_type="Button", replace=True)
    assert ok
    assert nav.calls == [
        ["idb", "ui", "set-value", "170", "222", "--value", "x", "--api", "ax", "--udid", "U"]
    ]


def test_set_value_on_old_idb_says_how_to_upgrade(press_nav, monkeypatch):
    monkeypatch.setattr(navigator, "idb_supports_set_value", lambda: False)
    ok, message = press_nav.find_and_enter_text("x", identifier="searchField", replace=True)
    assert not ok
    assert "idb 1.7+" in message and "brew upgrade" in message
    assert press_nav.calls == []
