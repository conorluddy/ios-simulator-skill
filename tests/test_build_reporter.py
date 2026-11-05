"""Unit tests for build/test output: runner failures reported as NOT RUN, and hints."""

from xcode.reporter import OutputFormatter, is_runner_failure

CLONE_TIMEOUT = (
    "Failed to prepare device 'Clone 1 of iPhone 17 Pro' for impending launch. "
    "(Underlying Error: Timed out trying to boot simulator after waiting 60.00s.))"
)
CLONE_MISSING = (
    "No matching device (8DDBB245-5BF6-4A64-A2FF-C2E177139A86) in set at "
    "/Users/me/Library/Developer/XCTestDevices"
)
NO_TESTS_PASSED = {"total": 2, "passed": 0, "failed": 2, "duration": 61.0}


def test_clone_boot_errors_with_nothing_passed_are_a_runner_failure():
    errors = [{"message": CLONE_TIMEOUT}, {"message": CLONE_MISSING}]
    assert is_runner_failure(errors, NO_TESTS_PASSED)


def test_runner_failure_without_test_results_still_counts():
    assert is_runner_failure([{"message": CLONE_TIMEOUT}], None)


def test_a_real_assertion_failure_is_not_a_runner_failure():
    errors = [{"message": CLONE_TIMEOUT}, {"message": "XCTAssertEqual failed: (1) is not (2)"}]
    assert not is_runner_failure(errors, NO_TESTS_PASSED)


def test_some_tests_passing_is_not_a_runner_failure():
    passed_one = {**NO_TESTS_PASSED, "passed": 1}
    assert not is_runner_failure([{"message": CLONE_TIMEOUT}], passed_one)


def test_runner_failure_prints_not_run_with_no_parallel_hint():
    output = OutputFormatter.format_minimal(
        status="FAILED",
        error_count=1,
        warning_count=0,
        xcresult_id="xcresult-1",
        test_info=NO_TESTS_PASSED,
        errors=[{"message": CLONE_TIMEOUT}],
        runner_failed=True,
    )
    assert output.startswith("Tests: NOT RUN (test runner couldn't start on the simulator)")
    assert "FAIL (" not in output
    assert "--no-parallel" in output


def test_hints_name_no_specific_device():
    errors = [
        {"type": "provisioning", "message": "x"},
        {"type": "build", "message": "Unable to find a destination"},
    ]
    hints = "\n".join(OutputFormatter.generate_hints(errors))
    assert "--simulator '<name>'" in hints
    assert "iPhone" not in hints
