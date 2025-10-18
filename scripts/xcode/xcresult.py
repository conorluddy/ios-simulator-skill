"""
XCResult bundle parser.

Extracts structured data from xcresult bundles using xcresulttool.
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class XCResultParser:
    """
    Parse xcresult bundles to extract build/test data.

    Uses xcresulttool to extract structured JSON data from Apple's
    xcresult bundle format.
    """

    def __init__(self, xcresult_path: Path, stderr: str = ""):
        """
        Initialize parser.

        Args:
            xcresult_path: Path to xcresult bundle
            stderr: Optional stderr output for fallback parsing
        """
        self.xcresult_path = xcresult_path
        self.stderr = stderr

        if xcresult_path and not xcresult_path.exists():
            raise FileNotFoundError(f"XCResult bundle not found: {xcresult_path}")

    def get_build_results(self) -> Optional[Dict]:
        """
        Get build results as JSON.

        Returns:
            Parsed JSON dict or None on error
        """
        return self._run_xcresulttool(['get', 'build-results'])

    def get_test_results(self) -> Optional[Dict]:
        """
        Get test results summary as JSON.

        Returns:
            Parsed JSON dict or None on error
        """
        return self._run_xcresulttool(['get', 'test-results', 'summary'])

    def get_build_log(self) -> Optional[str]:
        """
        Get build log as plain text.

        Returns:
            Build log string or None on error
        """
        result = self._run_xcresulttool(['get', 'log', '--type', 'build'], parse_json=False)
        return result if result else None

    def count_issues(self) -> Tuple[int, int]:
        """
        Count errors and warnings from build results.

        Returns:
            Tuple of (error_count, warning_count)
        """
        error_count = 0
        warning_count = 0

        build_results = self.get_build_results()

        if build_results:
            try:
                # Navigate JSON: actions[0].buildResult.issues
                actions = build_results.get('actions', {}).get('_values', [])
                if actions:
                    build_result = actions[0].get('buildResult', {})
                    issues = build_result.get('issues', {})

                    # Count errors
                    error_summaries = issues.get('errorSummaries', {}).get('_values', [])
                    error_count = len(error_summaries)

                    # Count warnings
                    warning_summaries = issues.get('warningSummaries', {}).get('_values', [])
                    warning_count = len(warning_summaries)

            except (KeyError, IndexError, TypeError) as e:
                print(f"Warning: Could not parse issue counts from xcresult: {e}", file=sys.stderr)

        # If no errors found in xcresult but stderr available, count stderr errors
        if error_count == 0 and self.stderr:
            stderr_errors = self._parse_stderr_errors()
            error_count = len(stderr_errors)

        return (error_count, warning_count)

    def get_errors(self) -> List[Dict]:
        """
        Get detailed error information.

        Returns:
            List of error dicts with message, file, line info
        """
        build_results = self.get_build_results()
        errors = []

        # Try to get errors from xcresult
        if build_results:
            try:
                actions = build_results.get('actions', {}).get('_values', [])
                if actions:
                    build_result = actions[0].get('buildResult', {})
                    issues = build_result.get('issues', {})
                    error_summaries = issues.get('errorSummaries', {}).get('_values', [])

                    for error in error_summaries:
                        errors.append({
                            'message': error.get('message', {}).get('_value', 'Unknown error'),
                            'type': error.get('issueType', {}).get('_value', 'error'),
                            'location': self._extract_location(error)
                        })

            except (KeyError, IndexError, TypeError) as e:
                print(f"Warning: Could not parse errors from xcresult: {e}", file=sys.stderr)

        # If no errors found in xcresult but stderr available, parse stderr
        if not errors and self.stderr:
            errors = self._parse_stderr_errors()

        return errors

    def get_warnings(self) -> List[Dict]:
        """
        Get detailed warning information.

        Returns:
            List of warning dicts with message, file, line info
        """
        build_results = self.get_build_results()
        if not build_results:
            return []

        warnings = []

        try:
            actions = build_results.get('actions', {}).get('_values', [])
            if not actions:
                return []

            build_result = actions[0].get('buildResult', {})
            issues = build_result.get('issues', {})
            warning_summaries = issues.get('warningSummaries', {}).get('_values', [])

            for warning in warning_summaries:
                warnings.append({
                    'message': warning.get('message', {}).get('_value', 'Unknown warning'),
                    'type': warning.get('issueType', {}).get('_value', 'warning'),
                    'location': self._extract_location(warning)
                })

        except (KeyError, IndexError, TypeError) as e:
            print(f"Warning: Could not parse warnings: {e}", file=sys.stderr)

        return warnings

    def _extract_location(self, issue: Dict) -> Dict:
        """
        Extract file location from issue.

        Args:
            issue: Issue dict from xcresult

        Returns:
            Location dict with file, line, column
        """
        location = {'file': None, 'line': None, 'column': None}

        try:
            doc_location = issue.get('documentLocationInCreatingWorkspace', {})
            location['file'] = doc_location.get('url', {}).get('_value')
            location['line'] = doc_location.get('startingLineNumber', {}).get('_value')
            location['column'] = doc_location.get('startingColumnNumber', {}).get('_value')
        except (KeyError, TypeError):
            pass

        return location

    def _run_xcresulttool(self, args: List[str], parse_json: bool = True) -> Optional[any]:
        """
        Run xcresulttool command.

        Args:
            args: Command arguments (after 'xcresulttool')
            parse_json: Whether to parse output as JSON

        Returns:
            Parsed JSON dict, plain text, or None on error
        """
        if not self.xcresult_path:
            return None

        cmd = ['xcrun', 'xcresulttool'] + args + ['--path', str(self.xcresult_path)]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            if parse_json:
                return json.loads(result.stdout)
            else:
                return result.stdout

        except subprocess.CalledProcessError as e:
            print(f"Error running xcresulttool: {e}", file=sys.stderr)
            print(f"stderr: {e.stderr}", file=sys.stderr)
            return None
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from xcresulttool: {e}", file=sys.stderr)
            return None

    def _parse_stderr_errors(self) -> List[Dict]:
        """
        Parse common errors from stderr output as fallback.

        Returns:
            List of error dicts parsed from stderr
        """
        errors = []

        if not self.stderr:
            return errors

        # Pattern 1: xcodebuild top-level errors (e.g., "xcodebuild: error: Unable to find...")
        xcodebuild_error_pattern = r"xcodebuild:\s*error:\s*(?P<message>.*?)(?:\n\n|\Z)"
        for match in re.finditer(xcodebuild_error_pattern, self.stderr, re.DOTALL):
            message = match.group('message').strip()
            # Clean up multi-line messages
            message = ' '.join(line.strip() for line in message.split('\n') if line.strip())
            errors.append({
                'message': message,
                'type': 'build',
                'location': {'file': None, 'line': None, 'column': None}
            })

        # Pattern 2: Provisioning profile errors
        provisioning_pattern = r"error:.*?provisioning profile.*?(?:doesn't|does not|cannot).*?(?P<message>.*?)(?:\n|$)"
        for match in re.finditer(provisioning_pattern, self.stderr, re.IGNORECASE):
            errors.append({
                'message': f"Provisioning profile error: {match.group('message').strip()}",
                'type': 'provisioning',
                'location': {'file': None, 'line': None, 'column': None}
            })

        # Pattern 3: Code signing errors
        signing_pattern = r"error:.*?(?:code sign|signing).*?(?P<message>.*?)(?:\n|$)"
        for match in re.finditer(signing_pattern, self.stderr, re.IGNORECASE):
            errors.append({
                'message': f"Code signing error: {match.group('message').strip()}",
                'type': 'signing',
                'location': {'file': None, 'line': None, 'column': None}
            })

        # Pattern 4: Generic compilation errors (but not if already captured)
        if not errors:
            generic_error_pattern = r"^(?:\*\*\s)?(?:error|❌):\s*(?P<message>.*?)(?:\n|$)"
            for match in re.finditer(generic_error_pattern, self.stderr, re.MULTILINE):
                message = match.group('message').strip()
                errors.append({
                    'message': message,
                    'type': 'build',
                    'location': {'file': None, 'line': None, 'column': None}
                })

        # Pattern 5: Specific "No profiles" error
        if 'No profiles for' in self.stderr:
            no_profile_pattern = r"No profiles for '(?P<bundle_id>.*?)' were found"
            for match in re.finditer(no_profile_pattern, self.stderr):
                errors.append({
                    'message': f"No provisioning profile found for bundle ID '{match.group('bundle_id')}'",
                    'type': 'provisioning',
                    'location': {'file': None, 'line': None, 'column': None}
                })

        return errors
