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


def test_exact_tap_presses_the_exact_label(nav):
    ok, _ = nav.find_and_tap(text="General Settings", fuzzy=False)
    assert ok
    assert nav.calls == [
        ["idb", "ui", "tap", "General Settings", "--match-key", "AXLabel", "--api", "ax"]
        + ["--udid", "U"]
    ]


def test_label_shared_with_a_container_falls_back_to_coordinates(nav):
    # The Group and the Application are also labelled "Settings".
    ok, _ = nav.find_and_tap(text="Settings", element_type="Button")
    assert ok
    assert nav.calls == [["idb", "ui", "tap", "60", "40", "--udid", "U"]]


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


def _idb_applies_set_value(monkeypatch, nav, tree, sticks=True):
    """Fake idb whose set-value updates the tree, so the read-back sees it (unless not sticks)."""
    import copy

    live_tree = copy.deepcopy(tree)

    def fake_run(cmd):
        nav.calls.append(cmd)
        if sticks and cmd[:3] == ["idb", "ui", "set-value"]:
            value = cmd[cmd.index("--value") + 1]
            for node in navigator._iter_nodes(live_tree):
                if node.get("AXUniqueId") == cmd[3] or _centre_matches(node, cmd[3:5]):
                    node["AXValue"] = value
        return (True, "")

    monkeypatch.setattr(navigator, "run_idb", fake_run)
    monkeypatch.setattr(navigator, "get_accessibility_tree", lambda udid, nested: live_tree)
    monkeypatch.setattr(navigator, "VALUE_READ_BACK_DELAY_SECONDS", 0)


def _centre_matches(node, xy):
    frame = node.get("frame") or {}
    if not frame or not all(part.isdigit() for part in xy):
        return False
    centre = (int(frame["x"] + frame["width"] / 2), int(frame["y"] + frame["height"] / 2))
    return centre == (int(xy[0]), int(xy[1]))


def test_set_value_addresses_field_by_unique_identifier(press_nav, monkeypatch):
    _idb_applies_set_value(monkeypatch, press_nav, OVERLAY_TREE)
    ok, message = press_nav.find_and_enter_text("Zürich", identifier="searchField", replace=True)
    assert ok
    assert message == 'Set value of: TextField "Search"'
    assert press_nav.calls == [
        ["idb", "ui", "set-value", "searchField", *MARKER_ARGS, "--value", "Zürich", "--udid", "U"]
    ]


def test_set_value_without_identifier_uses_coordinates(nav, monkeypatch):
    monkeypatch.setattr(navigator, "idb_supports_set_value", lambda: True)
    _idb_applies_set_value(monkeypatch, nav, SETTINGS_TREE)
    ok, _ = nav.find_and_enter_text("x", find_text="Settings", element_type="Button", replace=True)
    assert ok
    assert nav.calls == [
        ["idb", "ui", "set-value", "60", "40", "--value", "x", "--api", "ax", "--udid", "U"]
    ]


def test_set_value_on_old_idb_says_how_to_upgrade(press_nav, monkeypatch):
    monkeypatch.setattr(navigator, "idb_supports_set_value", lambda: False)
    ok, message = press_nav.find_and_enter_text("x", identifier="searchField", replace=True)
    assert not ok
    assert "idb 1.7+" in message and "brew upgrade" in message
    assert press_nav.calls == []


# === Toggles and the --expect guard ===


TOGGLE_TREE = _node(
    "Application",
    "Settings",
    0,
    0,
    400,
    800,
    [_with_id(_node("CheckBox", "Smart Punctuation", 36, 259, 330, 28), "SmartTyping")],
)
TOGGLE_TREE["children"][0]["AXValue"] = "1"


@pytest.fixture
def toggle_nav(monkeypatch):
    """Navigator over a screen with one toggle that is on."""
    calls: list[list[str]] = []

    def fake_run(cmd):
        calls.append(cmd)
        return (True, "")

    monkeypatch.setattr(navigator, "get_accessibility_tree", lambda udid, nested: TOGGLE_TREE)
    monkeypatch.setattr(navigator, "run_idb", fake_run)
    instance = Navigator("U")
    instance.calls = calls
    return instance


def test_toggle_reported_as_checkbox_is_pressed(toggle_nav):
    ok, message = toggle_nav.find_and_tap(identifier="SmartTyping")
    assert ok
    assert "accessibility press" in message
    assert toggle_nav.calls[0][:4] == ["idb", "ui", "tap", "SmartTyping"]


def test_expect_taps_when_value_matches(toggle_nav):
    ok, _ = toggle_nav.find_and_tap(identifier="SmartTyping", expected_value="1")
    assert ok
    assert len(toggle_nav.calls) == 1


def test_expect_refuses_to_tap_when_value_differs(toggle_nav):
    ok, message = toggle_nav.find_and_tap(identifier="SmartTyping", expected_value="0")
    assert not ok
    assert message == "Not tapped: CheckBox \"Smart Punctuation\" has value '1', expected '0'"
    assert toggle_nav.calls == []


SHARED_MARKER_TREE = _node(
    "Application",
    "Keyboards",
    0,
    0,
    400,
    800,
    [
        _with_id(_node("CheckBox", "Shortcut", 36, 375, 330, 28), "PeriodShortcut"),
        _with_id(_node("StaticText", "Adds a period", 36, 410, 330, 20), "PeriodShortcut"),
        _with_id(_node("CheckBox", "Sound", 36, 481, 330, 28), "keyboard-audio-x"),
        _with_id(_node("CheckBox", "Sound", 36, 520, 330, 28), "keyboard-audio"),
    ],
)


def test_toggle_with_shared_identifier_is_pressed_by_label(press_nav, monkeypatch):
    monkeypatch.setattr(
        navigator, "get_accessibility_tree", lambda udid, nested: SHARED_MARKER_TREE
    )
    ok, message = press_nav.find_and_tap(text="Shortcut", element_type="CheckBox")
    assert ok
    assert "accessibility press" in message
    assert press_nav.calls == [
        ["idb", "ui", "tap", "Shortcut", "--match-key", "AXLabel", *MARKER_ARGS[2:], "--udid", "U"]
    ]


def test_toggle_without_unique_marker_warns_after_coordinate_tap(press_nav, monkeypatch):
    monkeypatch.setattr(
        navigator, "get_accessibility_tree", lambda udid, nested: SHARED_MARKER_TREE
    )
    ok, message = press_nav.find_and_tap(identifier="keyboard-audio")
    assert ok
    assert press_nav.calls == [["idb", "ui", "tap", "201", "534", "--udid", "U"]]
    assert "toggles ignore coordinate taps" in message


# === Stuck tree (facebook/idb#964) ===

STUCK_TREE = _node("Application", None, 0, 0, 0, 0)


def test_stuck_tree_says_so_instead_of_not_found(nav, monkeypatch):
    monkeypatch.setattr(navigator, "get_accessibility_tree", lambda udid, nested: STUCK_TREE)
    ok, message = nav.find_and_tap(text="General")
    assert not ok
    assert message == navigator.STUCK_TREE_HINT
    assert nav.calls == []


def test_missing_element_on_a_real_screen_still_says_not_found(nav):
    ok, message = nav.find_and_tap(text="Nowhere")
    assert not ok
    assert message == "Not found: text='Nowhere'"


def test_stuck_tree_detection():
    assert navigator.is_stuck_tree(STUCK_TREE)
    assert not navigator.is_stuck_tree(SETTINGS_TREE)


def test_untyped_node_sharing_a_label_blocks_the_press(nav, monkeypatch):
    # idb's marker search sees untyped nodes too, so "General Settings" is ambiguous here.
    untyped = {"AXLabel": "General Settings", "frame": {}, "children": []}
    tree = dict(SETTINGS_TREE, children=[*SETTINGS_TREE["children"], untyped])
    monkeypatch.setattr(navigator, "get_accessibility_tree", lambda udid, nested: tree)
    ok, _ = nav.find_and_tap(text="General Settings", fuzzy=False)
    assert ok
    assert nav.calls == [["idb", "ui", "tap", "170", "222", "--udid", "U"]]


def test_set_value_that_does_not_stick_fails_with_what_it_reads(press_nav, monkeypatch):
    _idb_applies_set_value(monkeypatch, press_nav, OVERLAY_TREE, sticks=False)
    ok, message = press_nav.find_and_enter_text("Zürich", identifier="searchField", replace=True)
    assert not ok
    assert "didn't stick (reads None)" in message
    assert "\n" not in message


def test_secure_field_value_is_not_read_back(press_nav, monkeypatch):
    secure = _with_id(_node("SecureTextField", "Password", 28, 100, 346, 28), "password")
    tree = dict(OVERLAY_TREE, children=[*OVERLAY_TREE["children"], secure])
    _idb_applies_set_value(monkeypatch, press_nav, tree, sticks=False)
    ok, _ = press_nav.find_and_enter_text(
        "hunter2", identifier="password", element_type="SecureTextField", replace=True
    )
    assert ok


def test_read_back_follows_a_field_that_moves_once_edited():
    before = navigator.Element("TextField", "Search", None, None, {"x": 28, "y": 808}, [])
    after = navigator.Element("TextField", "Search", "Zürich", None, {"x": 8, "y": 498}, [])
    assert navigator._is_same_element(after, before)
