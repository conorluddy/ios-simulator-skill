"""Unit tests for BuildRunner's --run introspection: built app and destination UDID."""

import json
import subprocess

from xcode.builder import BuildRunner

SIMCTL_DEVICES = {
    "devices": {
        "com.apple.CoreSimulator.SimRuntime.iOS-26-5": [{"name": "iPhone 17 Pro", "udid": "OLD"}],
        "com.apple.CoreSimulator.SimRuntime.iOS-27-0": [{"name": "iPhone 17 Pro", "udid": "NEW"}],
    }
}


def _settings(extension: str, product: str, bundle_id: str) -> dict:
    return {
        "target": product,
        "buildSettings": {
            "WRAPPER_EXTENSION": extension,
            "TARGET_BUILD_DIR": "/DerivedData/Build/Products/Debug-iphonesimulator",
            "FULL_PRODUCT_NAME": f"{product}.{extension}",
            "PRODUCT_BUNDLE_IDENTIFIER": bundle_id,
        },
    }


def _fake_run(monkeypatch, build_settings: list[dict] | None = None):
    def run(cmd, **_kwargs):
        payload = build_settings if "-showBuildSettings" in cmd else SIMCTL_DEVICES
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", run)


def _runner(**kwargs) -> BuildRunner:
    return BuildRunner(project_path="My.xcodeproj", scheme="MyApp", **kwargs)


def test_built_app_reports_app_path_and_bundle_id(monkeypatch):
    _fake_run(monkeypatch, [_settings("app", "MyApp", "com.example.MyApp")])
    assert _runner(simulator="iPhone 17 Pro").get_built_app() == (
        "/DerivedData/Build/Products/Debug-iphonesimulator/MyApp.app",
        "com.example.MyApp",
    )


def test_built_app_picks_the_app_target_among_several(monkeypatch):
    _fake_run(
        monkeypatch,
        [
            _settings("framework", "Core", "com.example.Core"),
            _settings("app", "MyApp", "com.example.MyApp"),
            _settings("xctest", "MyAppTests", "com.example.MyAppTests"),
        ],
    )
    assert _runner(simulator="iPhone 17 Pro").get_built_app()[1] == "com.example.MyApp"


def test_built_app_is_none_without_an_app_target(monkeypatch):
    _fake_run(monkeypatch, [_settings("framework", "Core", "com.example.Core")])
    assert _runner(simulator="iPhone 17 Pro").get_built_app() is None


def test_destination_udid_matches_name_and_pinned_os(monkeypatch):
    _fake_run(monkeypatch)
    assert _runner(simulator="iPhone 17 Pro", os_version="26.5").get_destination_udid() == "OLD"
    assert _runner(simulator="iPhone 17 Pro").get_destination_udid() == "NEW"


def test_generic_destination_has_no_udid(monkeypatch):
    _fake_run(monkeypatch)
    runner = _runner()
    runner._destination = "generic/platform=iOS Simulator"
    assert runner.get_destination_udid() is None
