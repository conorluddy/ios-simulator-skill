"""Unit tests for gesture.py: swipe geometry, scroll semantics, idb argument shapes."""

from unittest import mock

import gesture
import pytest
from gesture import GestureController, compute_swipe_points

SCREEN = (400, 800)


@pytest.fixture
def idb_calls(monkeypatch):
    """Capture idb commands; every call succeeds."""
    calls: list[list[str]] = []

    def fake_run(cmd):
        calls.append(cmd)
        return (True, "")

    monkeypatch.setattr(gesture, "run_idb", fake_run)
    monkeypatch.setattr(gesture, "get_screen_size", lambda udid: SCREEN)
    monkeypatch.setattr(gesture.time, "sleep", lambda seconds: None)
    return calls


def _swipe_points(cmd: list[str]) -> tuple[int, int, int, int]:
    """Extract x1 y1 x2 y2 from an `idb ui swipe` command."""
    assert cmd[:3] == ["idb", "ui", "swipe"]
    return tuple(int(v) for v in cmd[3:7])


@pytest.mark.parametrize(
    ("direction", "axis", "sign"),
    [("up", 1, -1), ("down", 1, 1), ("left", 0, -1), ("right", 0, 1)],
)
def test_swipe_moves_finger_in_direction_for_70_percent(direction, axis, sign):
    start, end = compute_swipe_points(SCREEN, direction, 0.7)
    travel = end[axis] - start[axis]
    assert travel * sign > 0
    assert abs(travel) == pytest.approx(SCREEN[axis] * 0.7, abs=2)
    # The other axis stays put
    assert start[1 - axis] == end[1 - axis]


def test_swipe_never_reaches_screen_edges():
    start, end = compute_swipe_points(SCREEN, "up", 1.0)
    assert min(start[1], end[1]) >= SCREEN[1] * 0.05 - 1
    assert max(start[1], end[1]) <= SCREEN[1] * 0.95 + 1


def test_scroll_down_moves_finger_up(idb_calls):
    assert GestureController("U").scroll("down", amount=2)
    assert len(idb_calls) == 2
    x1, y1, x2, y2 = _swipe_points(idb_calls[0])
    assert y2 < y1  # finger travels up, revealing content below
    assert x1 == x2


def test_scroll_up_moves_finger_down(idb_calls):
    assert GestureController("U").scroll("up", amount=1)
    _, y1, _, y2 = _swipe_points(idb_calls[0])
    assert y2 > y1


def test_long_press_uses_tap_duration_in_seconds(idb_calls):
    assert GestureController("U").tap_and_hold(10, 20, duration_seconds=2.0)
    assert idb_calls == [["idb", "ui", "tap", "10", "20", "--duration", "2.0", "--udid", "U"]]


@pytest.mark.parametrize(("direction", "scale"), [("out", "2.0"), ("in", "0.5")])
def test_pinch_uses_native_idb_pinch(idb_calls, direction, scale):
    assert GestureController("U").pinch(direction)
    assert idb_calls == [["idb", "ui", "pinch", "200", "400", scale, "--udid", "U"]]


def test_explicit_pinch_scale_overrides_direction(idb_calls):
    assert GestureController("U").pinch("out", scale=0.25)
    assert idb_calls[0][5] == "0.25"


def test_double_tap_uses_multi_tap_with_count_two(idb_calls):
    assert GestureController("U").multi_tap(10, 20)
    assert idb_calls == [["idb", "ui", "multi-tap", "10", "20", "--count", "2", "--udid", "U"]]


def test_multi_tap_passes_explicit_count(idb_calls):
    assert GestureController("U").multi_tap(10, 20, count=3)
    assert idb_calls[0][5:7] == ["--count", "3"]


def test_multi_tap_rejects_single_tap(idb_calls):
    controller = GestureController("U")
    assert not controller.multi_tap(10, 20, count=1)
    assert "--tap-count" in controller.last_error
    assert idb_calls == []


def test_drag_between_points_passes_both_coordinate_pairs(idb_calls):
    assert GestureController("U").drag_and_drop((1, 2), (3, 4))
    assert idb_calls == [["idb", "ui", "drag-and-drop", "1", "2", "3", "4", "--udid", "U"]]


def test_drag_accepts_accessibility_labels_and_mixed_endpoints(idb_calls):
    controller = GestureController("U")
    assert controller.drag_and_drop("Row 1", "Row 4")
    assert controller.drag_and_drop("Row 1", (30, 40))
    assert idb_calls == [
        ["idb", "ui", "drag-and-drop", "Row 1", "Row 4", "--udid", "U"],
        ["idb", "ui", "drag-and-drop", "Row 1", "30", "40", "--udid", "U"],
    ]


def test_drag_endpoint_parsing_distinguishes_points_from_labels():
    assert gesture.parse_drag_endpoint("200,300", "--drag") == (200, 300)
    assert gesture.parse_drag_endpoint("Row 1", "--drag") == "Row 1"


def test_rotate_maps_name_to_idb_orientation(idb_calls):
    assert GestureController("U").rotate("landscape-left")
    assert idb_calls == [["idb", "ui", "rotate", "LANDSCAPE_LEFT", "--udid", "U"]]


def test_rotate_rejects_unknown_orientation(idb_calls):
    controller = GestureController("U")
    assert not controller.rotate("sideways")
    assert "choose from" in controller.last_error
    assert idb_calls == []


def test_shake(idb_calls):
    assert GestureController("U").shake()
    assert idb_calls == [["idb", "ui", "shake", "--udid", "U"]]


@pytest.mark.parametrize("method", ["shake", "rotate", "multi_tap", "drag_and_drop"])
def test_idb_1_7_commands_hint_at_upgrade_on_old_idb(monkeypatch, method):
    monkeypatch.setattr(gesture, "get_screen_size", lambda udid: SCREEN)
    monkeypatch.setattr(
        gesture, "run_idb", lambda cmd: (False, "error: argument ui_command: invalid choice: 'x'")
    )
    arguments = {
        "shake": (),
        "rotate": ("portrait",),
        "multi_tap": (1, 2),
        "drag_and_drop": ((1, 2), (3, 4)),
    }[method]
    controller = GestureController("U")
    assert not getattr(controller, method)(*arguments)
    assert "needs idb 1.7+" in controller.last_error


def test_other_failures_do_not_get_the_upgrade_hint(monkeypatch):
    monkeypatch.setattr(gesture, "get_screen_size", lambda udid: SCREEN)
    monkeypatch.setattr(gesture, "run_idb", lambda cmd: (False, "Connection refused"))
    controller = GestureController("U")
    assert not controller.shake()
    assert controller.last_error == "Connection refused"


def test_every_swipe_passes_a_duration(idb_calls):
    # idb has no default duration and iOS ignores an instantaneous swipe.
    controller = GestureController("U")
    assert controller.swipe("up")
    assert controller.scroll("down", amount=1)
    assert controller.refresh()
    for cmd in idb_calls:
        assert cmd[cmd.index("--duration") + 1] == "0.5"


def test_failed_gesture_keeps_idb_reason(monkeypatch):
    monkeypatch.setattr(gesture, "get_screen_size", lambda udid: SCREEN)
    monkeypatch.setattr(gesture, "run_idb", mock.Mock(return_value=(False, "Connection refused")))
    controller = GestureController("U")
    assert not controller.swipe("up")
    assert controller.last_error == "Connection refused"


def test_malformed_point_exits_with_message(capsys):
    with pytest.raises(SystemExit):
        gesture.parse_point("100", "--swipe-from")
    assert "--swipe-from expects x,y" in capsys.readouterr().err
