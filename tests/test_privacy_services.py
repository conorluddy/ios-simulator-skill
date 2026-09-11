"""Privacy service catalogue must match what `simctl privacy` actually accepts."""

import subprocess
from unittest.mock import patch

import pytest
from privacy_manager import (
    SERVICE_ALIASES,
    SUPPORTED_SERVICES,
    PrivacyManager,
    canonicalise_service,
)


class TestCanonicaliseService:
    def test_canonical_token_passes_through(self):
        assert canonicalise_service("camera") == "camera"

    def test_legacy_camel_case_alias_resolves(self):
        assert canonicalise_service("mediaLibrary") == "media-library"

    @pytest.mark.parametrize("service", ["health", "keyboard", "bluetooth", ""])
    def test_services_simctl_rejects_are_unsupported(self, service):
        assert canonicalise_service(service) is None

    def test_every_alias_targets_a_real_service(self):
        for alias, token in SERVICE_ALIASES.items():
            assert token in SUPPORTED_SERVICES, f"{alias} points at unknown {token}"


class TestApplyPermission:
    def test_unknown_service_never_shells_out(self):
        manager = PrivacyManager(udid="ABC123")
        with patch("subprocess.run") as run:
            success, message = manager.apply_permission("grant", "com.app", "health")
        run.assert_not_called()
        assert not success
        assert "Unknown service 'health'" in message

    def test_alias_is_translated_before_reaching_simctl(self):
        manager = PrivacyManager(udid="ABC123")
        with patch("subprocess.run") as run:
            success, _ = manager.apply_permission("grant", "com.app", "mediaLibrary")
        assert success
        assert run.call_args.args[0] == [
            "xcrun",
            "simctl",
            "privacy",
            "ABC123",
            "grant",
            "media-library",
            "com.app",
        ]

    def test_missing_udid_falls_back_to_booted(self):
        manager = PrivacyManager()
        with patch("subprocess.run") as run:
            manager.apply_permission("reset", "com.app", "photos")
        assert run.call_args.args[0][3] == "booted"

    def test_simctl_stderr_is_surfaced_on_failure(self):
        manager = PrivacyManager(udid="ABC123")
        failure = subprocess.CalledProcessError(1, "simctl", stderr="device not booted")
        with patch("subprocess.run", side_effect=failure):
            success, message = manager.apply_permission("grant", "com.app", "camera")
        assert not success
        assert "device not booted" in message
