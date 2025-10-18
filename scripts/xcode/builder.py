"""
Xcode build execution.

Handles xcodebuild command construction and execution with xcresult generation.
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

from .cache import XCResultCache


class BuildRunner:
    """
    Execute xcodebuild commands with xcresult bundle generation.

    Handles scheme auto-detection, command construction, and build/test execution.
    """

    def __init__(
        self,
        project_path: Optional[str] = None,
        workspace_path: Optional[str] = None,
        scheme: Optional[str] = None,
        configuration: str = "Debug",
        simulator: Optional[str] = None,
        cache: Optional[XCResultCache] = None
    ):
        """
        Initialize build runner.

        Args:
            project_path: Path to .xcodeproj
            workspace_path: Path to .xcworkspace
            scheme: Build scheme (auto-detected if not provided)
            configuration: Build configuration (Debug/Release)
            simulator: Simulator name
            cache: XCResult cache (creates default if not provided)
        """
        self.project_path = project_path
        self.workspace_path = workspace_path
        self.scheme = scheme
        self.configuration = configuration
        self.simulator = simulator
        self.cache = cache or XCResultCache()

    def auto_detect_scheme(self) -> Optional[str]:
        """
        Auto-detect build scheme from project/workspace.

        Returns:
            Detected scheme name or None
        """
        cmd = ['xcodebuild', '-list']

        if self.workspace_path:
            cmd.extend(['-workspace', self.workspace_path])
        elif self.project_path:
            cmd.extend(['-project', self.project_path])
        else:
            return None

        try:
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
        """
        Get xcodebuild destination string.

        Returns:
            Destination string for -destination flag
        """
        if self.simulator:
            return f"platform=iOS Simulator,name={self.simulator}"
        else:
            # Auto-detect best available simulator
            return self._auto_detect_simulator()

    def _auto_detect_simulator(self) -> str:
        """
        Auto-detect best available iOS simulator.

        Returns:
            Destination string for -destination flag
        """
        try:
            result = subprocess.run(
                ['xcrun', 'simctl', 'list', 'devices', 'available', 'iOS'],
                capture_output=True,
                text=True,
                check=True
            )

            # Parse available simulators, prefer latest iPhone
            # Looking for lines like: "iPhone 16 Pro (12345678-1234-1234-1234-123456789012) (Shutdown)"
            for line in result.stdout.split('\n'):
                if 'iPhone' in line and '(' in line:
                    # Extract device name
                    name = line.split('(')[0].strip()
                    if name:
                        return f"platform=iOS Simulator,name={name}"

            # Fallback to generic iOS Simulator if no iPhone found
            return "generic/platform=iOS Simulator"

        except subprocess.CalledProcessError as e:
            print(f"Warning: Could not auto-detect simulator: {e}", file=sys.stderr)
            return "generic/platform=iOS Simulator"

    def build(self, clean: bool = False) -> Tuple[bool, str, str]:
        """
        Build the project.

        Args:
            clean: Perform clean build

        Returns:
            Tuple of (success: bool, xcresult_id: str, stderr: str)
        """
        # Auto-detect scheme if needed
        if not self.scheme:
            self.scheme = self.auto_detect_scheme()
            if not self.scheme:
                print("Error: Could not auto-detect scheme. Use --scheme", file=sys.stderr)
                return (False, "", "")

        # Generate xcresult ID and path
        xcresult_id = self.cache.generate_id()
        xcresult_path = self.cache.get_path(xcresult_id)

        # Build command
        cmd = ['xcodebuild', '-quiet']  # Suppress verbose output

        if clean:
            cmd.append('clean')

        cmd.append('build')

        if self.workspace_path:
            cmd.extend(['-workspace', self.workspace_path])
        elif self.project_path:
            cmd.extend(['-project', self.project_path])
        else:
            print("Error: No project or workspace specified", file=sys.stderr)
            return (False, "", "")

        cmd.extend([
            '-scheme', self.scheme,
            '-configuration', self.configuration,
            '-destination', self.get_simulator_destination(),
            '-resultBundlePath', str(xcresult_path)
        ])

        # Execute build
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False  # Don't raise on non-zero exit
            )

            success = result.returncode == 0

            # xcresult bundle should be created even on failure
            if not xcresult_path.exists():
                print("Warning: xcresult bundle was not created", file=sys.stderr)
                return (success, "", result.stderr)

            return (success, xcresult_id, result.stderr)

        except Exception as e:
            print(f"Error executing build: {e}", file=sys.stderr)
            return (False, "", str(e))

    def test(self, test_suite: Optional[str] = None) -> Tuple[bool, str, str]:
        """
        Run tests.

        Args:
            test_suite: Specific test suite to run

        Returns:
            Tuple of (success: bool, xcresult_id: str, stderr: str)
        """
        # Auto-detect scheme if needed
        if not self.scheme:
            self.scheme = self.auto_detect_scheme()
            if not self.scheme:
                print("Error: Could not auto-detect scheme. Use --scheme", file=sys.stderr)
                return (False, "", "")

        # Generate xcresult ID and path
        xcresult_id = self.cache.generate_id()
        xcresult_path = self.cache.get_path(xcresult_id)

        # Build command
        cmd = ['xcodebuild', '-quiet', 'test']

        if self.workspace_path:
            cmd.extend(['-workspace', self.workspace_path])
        elif self.project_path:
            cmd.extend(['-project', self.project_path])
        else:
            print("Error: No project or workspace specified", file=sys.stderr)
            return (False, "", "")

        cmd.extend([
            '-scheme', self.scheme,
            '-destination', self.get_simulator_destination(),
            '-resultBundlePath', str(xcresult_path)
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

            success = result.returncode == 0

            # xcresult bundle should be created even on failure
            if not xcresult_path.exists():
                print("Warning: xcresult bundle was not created", file=sys.stderr)
                return (success, "", result.stderr)

            return (success, xcresult_id, result.stderr)

        except Exception as e:
            print(f"Error executing tests: {e}", file=sys.stderr)
            return (False, "", str(e))
