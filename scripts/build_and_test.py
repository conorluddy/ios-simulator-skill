#!/usr/bin/env python3
"""
Build and Test Automation for Xcode Projects

Wraps xcodebuild to provide token-efficient build and test execution with intelligent
error parsing and result summarization. Integrates with other scripts in this skill.

Features:
- Build Xcode projects and workspaces
- Run test suites with result parsing
- Clean builds with simulator selection
- Token-efficient summaries (3-5 lines by default)
- Integration with sim_health_check, test_recorder, app_launcher

Usage Examples:
    # Build project with auto-detected scheme
    python scripts/build_and_test.py --project MyApp.xcodeproj

    # Build workspace with specific scheme
    python scripts/build_and_test.py --workspace MyApp.xcworkspace --scheme MyApp

    # Run tests
    python scripts/build_and_test.py --project MyApp.xcodeproj --test

    # Clean build with simulator selection
    python scripts/build_and_test.py --project MyApp.xcodeproj --clean --simulator "iPhone 15 Pro"

    # Verbose output
    python scripts/build_and_test.py --project MyApp.xcodeproj --verbose
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class BuildAndTest:
    """Xcode build and test automation with intelligent result parsing."""

    def __init__(
        self,
        project_path: Optional[str] = None,
        workspace_path: Optional[str] = None,
        scheme: Optional[str] = None,
        simulator: Optional[str] = None,
        configuration: str = "Debug"
    ):
        """
        Initialize build configuration.

        Args:
            project_path: Path to .xcodeproj file
            workspace_path: Path to .xcworkspace file
            scheme: Build scheme name (auto-detected if not provided)
            simulator: Simulator name (uses booted if not specified)
            configuration: Build configuration (Debug or Release)
        """
        self.project_path = project_path
        self.workspace_path = workspace_path
        self.scheme = scheme
        self.simulator = simulator
        self.configuration = configuration
        self.build_output: List[str] = []
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.test_results: Dict = {}

    def auto_detect_scheme(self) -> Optional[str]:
        """Auto-detect build scheme from project/workspace."""
        try:
            cmd = ['xcodebuild', '-list']

            if self.workspace_path:
                cmd.extend(['-workspace', self.workspace_path])
            elif self.project_path:
                cmd.extend(['-project', self.project_path])
            else:
                return None

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            # Parse schemes from output
            in_schemes_section = False
            for line in result.stdout.split('\n'):
                line = line.strip()

                if 'Schemes:' in line:
                    in_schemes_section = True
                    continue

                if in_schemes_section and line and not line.startswith('Build'):
                    # First scheme in list
                    return line

        except subprocess.CalledProcessError as e:
            print(f"Error auto-detecting scheme: {e}", file=sys.stderr)

        return None

    def get_simulator_destination(self) -> str:
        """Get xcodebuild destination string for simulator."""
        if self.simulator:
            return f"platform=iOS Simulator,name={self.simulator}"
        else:
            # Use generic simulator (xcodebuild will pick one)
            return "platform=iOS Simulator,name=iPhone 15"

    def parse_build_output(self, output: str):
        """Parse xcodebuild output to extract errors and warnings."""
        self.build_output = output.split('\n')
        self.errors = []
        self.warnings = []

        # Common error patterns
        error_patterns = [
            r'❌\s+(.+)',  # Emoji error marker
            r'error:\s+(.+)',  # Standard error
            r'\*\* BUILD FAILED \*\*',  # Build failed
            r'Undefined symbols',  # Linker error
            r'No such file or directory',  # Missing file
        ]

        # Warning patterns
        warning_patterns = [
            r'⚠️\s+(.+)',  # Emoji warning marker
            r'warning:\s+(.+)',  # Standard warning
        ]

        for line in self.build_output:
            # Check for errors
            for pattern in error_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self.errors.append(line.strip())
                    break

            # Check for warnings
            for pattern in warning_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self.warnings.append(line.strip())
                    break

    def parse_test_results(self, output: str):
        """Parse xcodebuild test output to extract results."""
        lines = output.split('\n')

        # Initialize test results
        self.test_results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'duration': 0.0,
            'failures': []
        }

        # Parse test summary
        for line in lines:
            # Look for test execution summary
            if 'Test Suite' in line and 'passed' in line.lower():
                # Example: "Test Suite 'All tests' passed at 2025-10-18 14:30:00.000."
                match = re.search(r'(\d+) test[s]?,\s*(\d+) failure[s]?', line)
                if match:
                    self.test_results['total'] = int(match.group(1))
                    self.test_results['failed'] = int(match.group(2))
                    self.test_results['passed'] = self.test_results['total'] - self.test_results['failed']

            # Test duration
            if 'Executed in' in line or 'Test session duration' in line:
                match = re.search(r'([\d.]+)\s*second[s]?', line)
                if match:
                    self.test_results['duration'] = float(match.group(1))

            # Individual test failures
            if line.strip().startswith('✗') or 'failed' in line.lower():
                self.test_results['failures'].append(line.strip())

    def build(self, clean: bool = False) -> bool:
        """
        Build the project.

        Args:
            clean: Perform clean build

        Returns:
            True if build succeeded, False otherwise
        """
        # Auto-detect scheme if not provided
        if not self.scheme:
            self.scheme = self.auto_detect_scheme()
            if not self.scheme:
                print("Error: Could not auto-detect scheme. Please specify with --scheme", file=sys.stderr)
                return False

        # Build xcodebuild command
        cmd = ['xcodebuild']

        if clean:
            cmd.append('clean')

        cmd.append('build')

        if self.workspace_path:
            cmd.extend(['-workspace', self.workspace_path])
        elif self.project_path:
            cmd.extend(['-project', self.project_path])
        else:
            print("Error: No project or workspace specified", file=sys.stderr)
            return False

        cmd.extend([
            '-scheme', self.scheme,
            '-configuration', self.configuration,
            '-destination', self.get_simulator_destination()
        ])

        # Execute build
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False  # Don't raise on non-zero exit
            )

            # Combine stdout and stderr
            full_output = result.stdout + '\n' + result.stderr
            self.parse_build_output(full_output)

            return result.returncode == 0

        except Exception as e:
            print(f"Error executing build: {e}", file=sys.stderr)
            return False

    def test(self, test_suite: Optional[str] = None) -> bool:
        """
        Run tests.

        Args:
            test_suite: Specific test suite/class to run (runs all if not specified)

        Returns:
            True if all tests passed, False otherwise
        """
        # Auto-detect scheme if not provided
        if not self.scheme:
            self.scheme = self.auto_detect_scheme()
            if not self.scheme:
                print("Error: Could not auto-detect scheme. Please specify with --scheme", file=sys.stderr)
                return False

        # Build xcodebuild test command
        cmd = ['xcodebuild', 'test']

        if self.workspace_path:
            cmd.extend(['-workspace', self.workspace_path])
        elif self.project_path:
            cmd.extend(['-project', self.project_path])

        cmd.extend([
            '-scheme', self.scheme,
            '-destination', self.get_simulator_destination()
        ])

        if test_suite:
            cmd.extend(['-only-testing', test_suite])

        # Execute tests
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )

            # Parse test results
            full_output = result.stdout + '\n' + result.stderr
            self.parse_test_results(full_output)
            self.parse_build_output(full_output)  # Also get build errors

            return result.returncode == 0

        except Exception as e:
            print(f"Error executing tests: {e}", file=sys.stderr)
            return False

    def get_summary(self, verbose: bool = False) -> str:
        """
        Get build/test summary.

        Args:
            verbose: Include full output

        Returns:
            Formatted summary string
        """
        lines = []

        if self.test_results.get('total', 0) > 0:
            # Test summary
            total = self.test_results['total']
            passed = self.test_results['passed']
            failed = self.test_results['failed']
            duration = self.test_results['duration']

            status = "PASS" if failed == 0 else "FAIL"
            lines.append(f"Tests: {status} ({passed}/{total} passed, {failed} failed, {duration:.1f}s)")

            if failed > 0 and self.test_results['failures']:
                lines.append(f"Failures: {len(self.test_results['failures'])}")
                if not verbose:
                    # Show first 3 failures
                    for failure in self.test_results['failures'][:3]:
                        lines.append(f"  - {failure}")
        else:
            # Build summary
            status = "SUCCESS" if len(self.errors) == 0 else "FAILED"
            lines.append(f"Build: {status}")

        # Errors and warnings
        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")
            if not verbose:
                # Show first 3 errors
                for error in self.errors[:3]:
                    lines.append(f"  {error[:100]}")  # Truncate long lines

        if self.warnings:
            lines.append(f"Warnings: {len(self.warnings)}")
            if not verbose and len(self.warnings) <= 3:
                for warning in self.warnings[:3]:
                    lines.append(f"  {warning[:100]}")

        # Verbose output
        if verbose and (self.errors or self.warnings):
            lines.append("\n=== Full Output ===")
            lines.extend(self.build_output[-100:])  # Last 100 lines

        return '\n'.join(lines)

    def get_json_output(self) -> Dict:
        """Get build/test results as JSON."""
        return {
            'success': len(self.errors) == 0,
            'scheme': self.scheme,
            'configuration': self.configuration,
            'errors': self.errors,
            'warnings': self.warnings,
            'test_results': self.test_results if self.test_results.get('total', 0) > 0 else None
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Build and test Xcode projects with token-efficient output',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build project
  python scripts/build_and_test.py --project MyApp.xcodeproj

  # Build workspace with specific scheme
  python scripts/build_and_test.py --workspace MyApp.xcworkspace --scheme MyApp

  # Run tests
  python scripts/build_and_test.py --project MyApp.xcodeproj --test

  # Clean build
  python scripts/build_and_test.py --project MyApp.xcodeproj --clean

  # Specific test suite
  python scripts/build_and_test.py --project MyApp.xcodeproj --test --suite LoginTests
        """
    )

    # Project/workspace selection
    project_group = parser.add_mutually_exclusive_group()
    project_group.add_argument('--project', help='Path to .xcodeproj file')
    project_group.add_argument('--workspace', help='Path to .xcworkspace file')

    # Build options
    parser.add_argument('--scheme', help='Build scheme (auto-detected if not specified)')
    parser.add_argument('--configuration', default='Debug', choices=['Debug', 'Release'],
                       help='Build configuration (default: Debug)')
    parser.add_argument('--simulator', help='Simulator name (default: iPhone 15)')
    parser.add_argument('--clean', action='store_true', help='Clean before building')

    # Test options
    parser.add_argument('--test', action='store_true', help='Run tests')
    parser.add_argument('--suite', help='Specific test suite to run (e.g., LoginTests)')

    # Output options
    parser.add_argument('--verbose', action='store_true', help='Show detailed output')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--output', help='Save results to file')

    args = parser.parse_args()

    # Validate inputs
    if not args.project and not args.workspace:
        # Try to auto-detect in current directory
        cwd = Path.cwd()
        projects = list(cwd.glob('*.xcodeproj'))
        workspaces = list(cwd.glob('*.xcworkspace'))

        if workspaces:
            args.workspace = str(workspaces[0])
        elif projects:
            args.project = str(projects[0])
        else:
            parser.error("No project or workspace specified and none found in current directory")

    # Initialize builder
    builder = BuildAndTest(
        project_path=args.project,
        workspace_path=args.workspace,
        scheme=args.scheme,
        simulator=args.simulator,
        configuration=args.configuration
    )

    # Execute build or test
    success = False
    if args.test:
        success = builder.test(test_suite=args.suite)
    else:
        success = builder.build(clean=args.clean)

    # Output results
    if args.json:
        output = json.dumps(builder.get_json_output(), indent=2)
        if args.output:
            Path(args.output).write_text(output)
            print(f"Results saved to: {args.output}")
        else:
            print(output)
    else:
        summary = builder.get_summary(verbose=args.verbose)
        if args.output:
            Path(args.output).write_text(summary)
            print(f"Results saved to: {args.output}")
        else:
            print(summary)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
