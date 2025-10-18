"""
Build/test output formatting.

Provides multiple output formats with progressive disclosure support.
"""

import json
import sys
from typing import Dict, List, Optional


class OutputFormatter:
    """
    Format build/test results for display.

    Supports ultra-minimal default output, verbose mode, and JSON output.
    """

    @staticmethod
    def format_minimal(
        status: str,
        error_count: int,
        warning_count: int,
        xcresult_id: str,
        test_info: Optional[Dict] = None
    ) -> str:
        """
        Format ultra-minimal output (5-10 tokens).

        Args:
            status: Build status (SUCCESS/FAILED)
            error_count: Number of errors
            warning_count: Number of warnings
            xcresult_id: XCResult bundle ID
            test_info: Optional test results dict

        Returns:
            Minimal formatted string

        Example:
            Build: SUCCESS (0 errors, 3 warnings) [xcresult-20251018-143052]
            Tests: PASS (12/12 passed, 4.2s) [xcresult-20251018-143052]
        """
        lines = []

        if test_info:
            # Test mode
            total = test_info.get('total', 0)
            passed = test_info.get('passed', 0)
            failed = test_info.get('failed', 0)
            duration = test_info.get('duration', 0.0)

            test_status = "PASS" if failed == 0 else "FAIL"
            lines.append(f"Tests: {test_status} ({passed}/{total} passed, {duration:.1f}s) [{xcresult_id}]")
        else:
            # Build mode
            lines.append(f"Build: {status} ({error_count} errors, {warning_count} warnings) [{xcresult_id}]")

        return '\n'.join(lines)

    @staticmethod
    def format_errors(errors: List[Dict], limit: int = 10) -> str:
        """
        Format error details.

        Args:
            errors: List of error dicts
            limit: Maximum errors to show

        Returns:
            Formatted error list
        """
        if not errors:
            return "No errors found."

        lines = [f"Errors ({len(errors)}):"]
        lines.append("")

        for i, error in enumerate(errors[:limit], 1):
            message = error.get('message', 'Unknown error')
            location = error.get('location', {})

            # Format location
            loc_parts = []
            if location.get('file'):
                file_path = location['file'].replace('file://', '')
                loc_parts.append(file_path)
            if location.get('line'):
                loc_parts.append(f"line {location['line']}")

            location_str = ':'.join(loc_parts) if loc_parts else 'unknown location'

            lines.append(f"{i}. {message}")
            lines.append(f"   Location: {location_str}")
            lines.append("")

        if len(errors) > limit:
            lines.append(f"... and {len(errors) - limit} more errors")

        return '\n'.join(lines)

    @staticmethod
    def format_warnings(warnings: List[Dict], limit: int = 10) -> str:
        """
        Format warning details.

        Args:
            warnings: List of warning dicts
            limit: Maximum warnings to show

        Returns:
            Formatted warning list
        """
        if not warnings:
            return "No warnings found."

        lines = [f"Warnings ({len(warnings)}):"]
        lines.append("")

        for i, warning in enumerate(warnings[:limit], 1):
            message = warning.get('message', 'Unknown warning')
            location = warning.get('location', {})

            # Format location
            loc_parts = []
            if location.get('file'):
                file_path = location['file'].replace('file://', '')
                loc_parts.append(file_path)
            if location.get('line'):
                loc_parts.append(f"line {location['line']}")

            location_str = ':'.join(loc_parts) if loc_parts else 'unknown location'

            lines.append(f"{i}. {message}")
            lines.append(f"   Location: {location_str}")
            lines.append("")

        if len(warnings) > limit:
            lines.append(f"... and {len(warnings) - limit} more warnings")

        return '\n'.join(lines)

    @staticmethod
    def format_log(log: str, lines: int = 50) -> str:
        """
        Format build log (show last N lines).

        Args:
            log: Full build log
            lines: Number of lines to show

        Returns:
            Formatted log excerpt
        """
        if not log:
            return "No build log available."

        log_lines = log.strip().split('\n')

        if len(log_lines) <= lines:
            return log

        # Show last N lines
        excerpt = log_lines[-lines:]
        return f"... (showing last {lines} lines of {len(log_lines)})\n\n" + '\n'.join(excerpt)

    @staticmethod
    def format_json(data: Dict) -> str:
        """
        Format data as JSON.

        Args:
            data: Data to format

        Returns:
            Pretty-printed JSON string
        """
        return json.dumps(data, indent=2)

    @staticmethod
    def format_verbose(
        status: str,
        error_count: int,
        warning_count: int,
        xcresult_id: str,
        errors: Optional[List[Dict]] = None,
        warnings: Optional[List[Dict]] = None,
        test_info: Optional[Dict] = None
    ) -> str:
        """
        Format verbose output with error/warning details.

        Args:
            status: Build status
            error_count: Error count
            warning_count: Warning count
            xcresult_id: XCResult ID
            errors: Optional error list
            warnings: Optional warning list
            test_info: Optional test results

        Returns:
            Verbose formatted output
        """
        lines = []

        # Header
        if test_info:
            total = test_info.get('total', 0)
            passed = test_info.get('passed', 0)
            failed = test_info.get('failed', 0)
            duration = test_info.get('duration', 0.0)

            test_status = "PASS" if failed == 0 else "FAIL"
            lines.append(f"Tests: {test_status}")
            lines.append(f"  Total: {total}")
            lines.append(f"  Passed: {passed}")
            lines.append(f"  Failed: {failed}")
            lines.append(f"  Duration: {duration:.1f}s")
        else:
            lines.append(f"Build: {status}")

        lines.append(f"XCResult: {xcresult_id}")
        lines.append("")

        # Errors
        if errors and len(errors) > 0:
            lines.append(OutputFormatter.format_errors(errors, limit=5))
            lines.append("")

        # Warnings
        if warnings and len(warnings) > 0:
            lines.append(OutputFormatter.format_warnings(warnings, limit=5))
            lines.append("")

        # Summary
        lines.append(f"Summary: {error_count} errors, {warning_count} warnings")

        return '\n'.join(lines)
