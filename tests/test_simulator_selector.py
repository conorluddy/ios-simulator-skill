"""Unit tests for simulator_selector version ordering."""

from simulator_selector import version_key


def test_versions_compare_numerically_not_lexically():
    assert max(["9.0", "26.2", "26.10", "18.1"], key=version_key) == "26.10"
