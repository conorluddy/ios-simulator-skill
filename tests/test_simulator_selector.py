"""Unit tests for simulator_selector version ordering and model ranking."""

from simulator_selector import SimulatorInfo, SimulatorSelector, version_key


def test_versions_compare_numerically_not_lexically():
    assert max(["9.0", "26.2", "26.10", "18.1"], key=version_key) == "26.10"


def test_newer_generation_outranks_older_pro():
    selector = SimulatorSelector()
    selector.last_used_simulator = None
    older_pro = SimulatorInfo("iPhone 16 Pro", "A", "27.0", "Shutdown")
    newer_base = SimulatorInfo("iPhone 17", "B", "27.0", "Shutdown")
    newer_pro = SimulatorInfo("iPhone 17 Pro", "C", "27.0", "Shutdown")
    selector.simulators = [older_pro, newer_base, newer_pro]
    scores = {sim.name: selector._score_simulator(sim) for sim in selector.simulators}
    assert scores["iPhone 17 Pro"] > scores["iPhone 17"] > scores["iPhone 16 Pro"]
