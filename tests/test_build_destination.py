"""Unit tests for BuildRunner simulator destination pinning."""

import json
import subprocess

from xcode.builder import BuildRunner

SIMCTL_DEVICES = {
    "devices": {
        "com.apple.CoreSimulator.SimRuntime.iOS-26-5": [
            {"name": "iPhone 17 Pro (iOS 26.5)", "udid": "A"},
            {"name": "iPhone 17 Pro (EN)", "udid": "B"},
            {"name": "iPhone 17 Pro", "udid": "C"},
        ],
        "com.apple.CoreSimulator.SimRuntime.iOS-27-0": [{"name": "iPhone 17 Pro", "udid": "D"}],
        "com.apple.CoreSimulator.SimRuntime.watchOS-26-5": [{"name": "iPhone 17 Pro", "udid": "E"}],
    }
}


def _fake_simctl(monkeypatch):
    def run(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 0, stdout=json.dumps(SIMCTL_DEVICES), stderr="")

    monkeypatch.setattr(subprocess, "run", run)


def test_device_on_older_runtime_is_pinned_to_its_os(monkeypatch):
    _fake_simctl(monkeypatch)
    destination = BuildRunner(simulator="iPhone 17 Pro (iOS 26.5)").get_simulator_destination()
    assert destination == "platform=iOS Simulator,name=iPhone 17 Pro (iOS 26.5),OS=26.5"


def test_name_on_several_runtimes_pins_the_newest(monkeypatch):
    _fake_simctl(monkeypatch)
    runner = BuildRunner()
    assert (
        runner._named_destination("iPhone 17 Pro")
        == "platform=iOS Simulator,name=iPhone 17 Pro,OS=27.0"
    )


def test_preferred_os_version_selects_that_runtime(monkeypatch):
    _fake_simctl(monkeypatch)
    runner = BuildRunner()
    destination = runner._named_destination("iPhone 17 Pro", "26.5")
    assert destination == "platform=iOS Simulator,name=iPhone 17 Pro,OS=26.5"


def test_name_match_is_exact_not_substring(monkeypatch):
    _fake_simctl(monkeypatch)
    assert BuildRunner()._find_simulator_os("iPhone 17") is None
