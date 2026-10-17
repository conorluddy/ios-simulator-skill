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
