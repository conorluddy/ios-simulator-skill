"""Unit tests for tree reads: backend selection, retry, screen size, screen_mapper coverage."""

import json
import subprocess

import pytest
import screen_mapper
from common import device_utils, idb_utils
from screen_mapper import ScreenMapper


def _node(node_type, label, x, y, width, height, children=(), **extra):
    return {
        "type": node_type,
        "AXLabel": label,
        "frame": {"x": x, "y": y, "width": width, "height": height},
        "enabled": True,
        "children": list(children),
        **extra,
    }


# Safari showing a page: web content is an unlabelled full-screen Sheet to `ax`.
SAFARI_TREE = _node(
    "Application",
    "Safari",
    0,
    0,
    402,
    874,
    [
        _node("Sheet", None, 0, 0, 402, 874),
        _node("Button", "Back", 16, 800, 44, 44),
        _node("Button", "Tabs", 340, 800, 44, 44),
    ],
)

SETTINGS_TREE = _node(
    "Application",
    "Settings",
    0,
    0,
    402,
    874,
    [_node("Button", f"Row {row}", 16, 100 + row * 52, 370, 52) for row in range(14)],
)


def _completed(stdout: str) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")


# === get_accessibility_tree ===


def test_tree_read_passes_backend_only_when_asked(monkeypatch):
    commands: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        commands.append(cmd)
        return _completed(json.dumps([SETTINGS_TREE]))

    monkeypatch.setattr(idb_utils.subprocess, "run", fake_run)
    idb_utils.get_accessibility_tree("U")
    idb_utils.get_accessibility_tree("U", api="axbridge")
    assert "--api" not in commands[0]
    assert commands[1][-4:] == ["--api", "axbridge", "--udid", "U"]


def test_tree_read_retries_once_after_non_json(monkeypatch):
    outputs = iter(["guest starting", json.dumps([SETTINGS_TREE])])
    monkeypatch.setattr(idb_utils.subprocess, "run", lambda cmd, **kw: _completed(next(outputs)))
    assert idb_utils.get_accessibility_tree("U")["AXLabel"] == "Settings"


def test_tree_read_reports_what_idb_printed(monkeypatch, capsys):
    monkeypatch.setattr(idb_utils.subprocess, "run", lambda cmd, **kw: _completed("not json"))
    with pytest.raises(SystemExit):
        idb_utils.get_accessibility_tree("U")
    assert "not json" in capsys.readouterr().err


# === get_device_screen_size ===


def test_screen_size_comes_from_target_description(monkeypatch):
    description = {"screen_dimensions": {"width_points": 402, "height_points": 874}}
    commands: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        commands.append(cmd)
        return _completed(json.dumps(description))

    monkeypatch.setattr(device_utils.subprocess, "run", fake_run)
    assert device_utils.get_device_screen_size("U") == (402, 874)
    assert commands == [["idb", "describe", "--json", "--udid", "U"]]


def test_zero_screen_size_falls_back(monkeypatch):
    description = {"screen_dimensions": {"width_points": 0, "height_points": 0}}
    monkeypatch.setattr(
        device_utils.subprocess, "run", lambda cmd, **kw: _completed(json.dumps(description))
    )
    assert device_utils.get_device_screen_size("U") == (390, 844)


# === screen_mapper coverage hint ===


def test_web_page_has_low_labelled_coverage():
    assert screen_mapper.labelled_leaf_coverage(SAFARI_TREE) < screen_mapper.LOW_COVERAGE_RATIO


def test_native_list_has_high_labelled_coverage():
    assert screen_mapper.labelled_leaf_coverage(SETTINGS_TREE) > 0.5


def test_summary_suggests_deep_when_screen_looks_empty():
    mapper = ScreenMapper("U")
    summary = mapper.format_summary(mapper.analyze_tree(SAFARI_TREE))
    assert "retry with --deep" in summary


def test_summary_omits_hint_on_deep_reads_and_full_screens():
    deep = ScreenMapper("U", deep=True)
    assert "--deep" not in deep.format_summary(deep.analyze_tree(SAFARI_TREE))
    mapper = ScreenMapper("U")
    assert "Coverage" not in mapper.format_summary(mapper.analyze_tree(SETTINGS_TREE))


def test_deep_read_counts_elements_with_null_enabled_as_focusable():
    tree = _node("Other", "Safari", 0, 0, 402, 874, [_node("Button", "Sign in", 0, 0, 60, 21)])
    tree["children"][0]["enabled"] = None
    analysis = ScreenMapper("U", deep=True).analyze_tree(tree)
    assert analysis["focusable"] == 1


def test_deep_mapper_reads_through_axbridge(monkeypatch):
    calls: list[str | None] = []

    def fake_tree(udid, nested, api=None):
        calls.append(api)
        return SETTINGS_TREE

    monkeypatch.setattr(screen_mapper, "get_accessibility_tree", fake_tree)
    ScreenMapper("U", deep=True).get_accessibility_tree()
    ScreenMapper("U").get_accessibility_tree()
    assert calls == ["axbridge", None]
