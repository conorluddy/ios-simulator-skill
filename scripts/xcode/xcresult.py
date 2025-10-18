"""
XCResult bundle parser.

Extracts structured data from xcresult bundles using xcresulttool.
"""

import json
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

    def __init__(self, xcresult_path: Path):
        """
        Initialize parser.

        Args:
            xcresult_path: Path to xcresult bundle
        """
        self.xcresult_path = xcresult_path

        if not xcresult_path.exists():
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
        build_results = self.get_build_results()
        if not build_results:
            return (0, 0)

        error_count = 0
        warning_count = 0

        try:
            # Navigate JSON: actions[0].buildResult.issues
            actions = build_results.get('actions', {}).get('_values', [])
            if not actions:
                return (0, 0)

            build_result = actions[0].get('buildResult', {})
            issues = build_result.get('issues', {})

            # Count errors
            error_summaries = issues.get('errorSummaries', {}).get('_values', [])
            error_count = len(error_summaries)

            # Count warnings
            warning_summaries = issues.get('warningSummaries', {}).get('_values', [])
            warning_count = len(warning_summaries)

        except (KeyError, IndexError, TypeError) as e:
            print(f"Warning: Could not parse issue counts: {e}", file=sys.stderr)

        return (error_count, warning_count)

    def get_errors(self) -> List[Dict]:
        """
        Get detailed error information.

        Returns:
            List of error dicts with message, file, line info
        """
        build_results = self.get_build_results()
        if not build_results:
            return []

        errors = []

        try:
            actions = build_results.get('actions', {}).get('_values', [])
            if not actions:
                return []

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
            print(f"Warning: Could not parse errors: {e}", file=sys.stderr)

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
