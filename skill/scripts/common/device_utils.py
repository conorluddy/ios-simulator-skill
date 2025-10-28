#!/usr/bin/env python3
"""
Shared device and simulator utilities.

Common patterns for interacting with simulators via xcrun simctl and IDB.
Standardizes command building and device targeting to prevent errors.

Follows Jackson's Law - only extracts genuinely reused patterns.

Used by:
- app_launcher.py (8 call sites) - App lifecycle commands
- Multiple scripts (15+ locations) - IDB command building
- navigator.py, gesture.py - Coordinate transformation
- test_recorder.py, app_state_capture.py - Auto-UDID detection
"""

import json
import re
import subprocess


def build_simctl_command(
    operation: str,
    udid: str | None = None,
    *args,
) -> list[str]:
    """
    Build xcrun simctl command with proper device handling.

    Standardizes command building to prevent device targeting bugs.
    Automatically uses "booted" if no UDID provided.

    Used by:
    - app_launcher.py: launch, terminate, install, uninstall, openurl, listapps, spawn
    - Multiple scripts: generic simctl operations

    Args:
        operation: simctl operation (launch, terminate, install, etc.)
        udid: Device UDID (uses 'booted' if None)
        *args: Additional command arguments

    Returns:
        Complete command list ready for subprocess.run()

    Examples:
        # Launch app on booted simulator
        cmd = build_simctl_command("launch", None, "com.app.bundle")
        # Returns: ["xcrun", "simctl", "launch", "booted", "com.app.bundle"]

        # Launch on specific device
        cmd = build_simctl_command("launch", "ABC123", "com.app.bundle")
        # Returns: ["xcrun", "simctl", "launch", "ABC123", "com.app.bundle"]

        # Install app on specific device
        cmd = build_simctl_command("install", "ABC123", "/path/to/app.app")
        # Returns: ["xcrun", "simctl", "install", "ABC123", "/path/to/app.app"]
    """
    cmd = ["xcrun", "simctl", operation]

    # Add device (booted or specific UDID)
    cmd.append(udid if udid else "booted")

    # Add remaining arguments
    cmd.extend(str(arg) for arg in args)

    return cmd


def build_idb_command(
    operation: str,
    udid: str | None = None,
    *args,
) -> list[str]:
    """
    Build IDB command with proper device targeting.

    Standardizes IDB command building across all scripts using IDB.
    Handles device UDID consistently.

    Used by:
    - navigator.py: ui tap, ui text, ui describe-all
    - gesture.py: ui swipe, ui tap
    - keyboard.py: ui key, ui text, ui tap
    - And more: 15+ locations

    Args:
        operation: IDB operation path (e.g., "ui tap", "ui text", "ui describe-all")
        udid: Device UDID (omits --udid flag if None, IDB uses booted by default)
        *args: Additional command arguments

    Returns:
        Complete command list ready for subprocess.run()

    Examples:
        # Tap on booted simulator
        cmd = build_idb_command("ui tap", None, "200", "400")
        # Returns: ["idb", "ui", "tap", "200", "400"]

        # Tap on specific device
        cmd = build_idb_command("ui tap", "ABC123", "200", "400")
        # Returns: ["idb", "ui", "tap", "200", "400", "--udid", "ABC123"]

        # Get accessibility tree
        cmd = build_idb_command("ui describe-all", "ABC123", "--json", "--nested")
        # Returns: ["idb", "ui", "describe-all", "--json", "--nested", "--udid", "ABC123"]

        # Enter text
        cmd = build_idb_command("ui text", None, "hello world")
        # Returns: ["idb", "ui", "text", "hello world"]
    """
    # Split operation into parts (e.g., "ui tap" -> ["ui", "tap"])
    cmd = ["idb"] + operation.split()

    # Add arguments
    cmd.extend(str(arg) for arg in args)

    # Add device targeting if specified (optional for IDB, uses booted by default)
    if udid:
        cmd.extend(["--udid", udid])

    return cmd


def get_booted_device_udid() -> str | None:
    """
    Auto-detect currently booted simulator UDID.

    Queries xcrun simctl for booted devices and returns first match.

    Returns:
        UDID of booted simulator, or None if no simulator is booted.

    Example:
        udid = get_booted_device_udid()
        if udid:
            print(f"Booted simulator: {udid}")
        else:
            print("No simulator is currently booted")
    """
    try:
        result = subprocess.run(
            ["xcrun", "simctl", "list", "devices", "booted"],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse output to find UDID
        # Format: "  iPhone 16 Pro (ABC123-DEF456) (Booted)"
        for line in result.stdout.split("\n"):
            # Look for UUID pattern in parentheses
            match = re.search(r"\(([A-F0-9\-]{36})\)", line)
            if match:
                return match.group(1)

        return None
    except subprocess.CalledProcessError:
        return None


def resolve_udid(udid_arg: str | None) -> str:
    """
    Resolve device UDID with auto-detection fallback.

    If udid_arg is provided, returns it immediately.
    If None, attempts to auto-detect booted simulator.
    Raises error if neither is available.

    Args:
        udid_arg: Explicit UDID from command line, or None

    Returns:
        Valid UDID string

    Raises:
        RuntimeError: If no UDID provided and no booted simulator found

    Example:
        try:
            udid = resolve_udid(args.udid)  # args.udid might be None
            print(f"Using device: {udid}")
        except RuntimeError as e:
            print(f"Error: {e}")
            sys.exit(1)
    """
    if udid_arg:
        return udid_arg

    booted_udid = get_booted_device_udid()
    if booted_udid:
        return booted_udid

    raise RuntimeError(
        "No device UDID provided and no simulator is currently booted.\n"
        "Boot a simulator or provide --udid explicitly:\n"
        "  xcrun simctl boot <device-name>\n"
        "  python scripts/script_name.py --udid <device-udid>"
    )


def get_device_screen_size(udid: str) -> tuple[int, int]:
    """
    Get actual screen dimensions for device via accessibility tree.

    Queries IDB accessibility tree to determine actual device resolution.
    Falls back to iPhone 14 defaults (390x844) if detection fails.

    Args:
        udid: Device UDID

    Returns:
        Tuple of (width, height) in pixels

    Example:
        width, height = get_device_screen_size("ABC123")
        print(f"Device screen: {width}x{height}")
    """
    try:
        cmd = build_idb_command("ui describe-all", udid, "--json")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Parse JSON response
        data = json.loads(result.stdout)
        tree = data[0] if isinstance(data, list) and len(data) > 0 else data

        # Get frame size from root element
        if tree and "frame" in tree:
            frame = tree["frame"]
            width = int(frame.get("width", 390))
            height = int(frame.get("height", 844))
            return (width, height)

        # Fallback
        return (390, 844)
    except Exception:
        # Graceful fallback to iPhone 14 Pro defaults
        return (390, 844)


def transform_screenshot_coords(
    x: float,
    y: float,
    screenshot_width: int,
    screenshot_height: int,
    device_width: int,
    device_height: int,
) -> tuple[int, int]:
    """
    Transform screenshot coordinates to device coordinates.

    Handles the case where a screenshot was downscaled (e.g., to 'half' size)
    and needs to be transformed back to actual device pixel coordinates
    for accurate tapping.

    The transformation is linear:
    device_x = (screenshot_x / screenshot_width) * device_width
    device_y = (screenshot_y / screenshot_height) * device_height

    Args:
        x, y: Coordinates in the screenshot
        screenshot_width, screenshot_height: Screenshot dimensions (e.g., 195, 422)
        device_width, device_height: Actual device dimensions (e.g., 390, 844)

    Returns:
        Tuple of (device_x, device_y) in device pixels

    Example:
        # Screenshot taken at 'half' size: 195x422 (from 390x844 device)
        device_x, device_y = transform_screenshot_coords(
            100, 200,  # Tap point in screenshot
            195, 422,  # Screenshot dimensions
            390, 844   # Device dimensions
        )
        print(f"Tap at device coords: ({device_x}, {device_y})")
        # Output: Tap at device coords: (200, 400)
    """
    device_x = int((x / screenshot_width) * device_width)
    device_y = int((y / screenshot_height) * device_height)
    return (device_x, device_y)
