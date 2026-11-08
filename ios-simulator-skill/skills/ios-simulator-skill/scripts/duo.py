#!/usr/bin/env python3
"""Read and set a booted iPhone Duo's hinge and interface orientation."""

import argparse
import json
import math
import sys
import time

from common.duo_backend import DuoBackend, command

POSES = {"closed": 0, "partial": 90, "open": 180}
ROTATIONS = {
    "portrait": "rot0",
    "landscape": "rot90",
    "portrait-upside-down": "rot180",
    "landscape-flipped": "rot270",
}


class DuoManager:
    """Require an explicit Duo target and verify every requested effect."""

    def __init__(self, udid: str, backend: DuoBackend | None = None):
        """Initialize with an explicit UDID; never choose another booted device."""
        self.udid = udid
        self.backend = backend if backend is not None else DuoBackend()

    def validate_device(self) -> None:
        """Reject shutdown, non-Duo and implicit targets before compiling or dispatching."""
        devices = json.loads(command(["xcrun", "simctl", "list", "devices", "booted", "-j"]))
        if not any(
            device.get("udid") == self.udid
            and device.get("state") == "Booted"
            and "iphone-duo" in device.get("deviceTypeIdentifier", "").lower()
            for group in devices["devices"].values()
            for device in group
        ):
            raise ValueError("Select an explicit booted iPhone Duo UDID with --udid")

    def read(self) -> dict:
        """Read hinge sensor and active display state independently of dispatch."""
        data = json.loads(
            command(
                [
                    "xcrun",
                    "devicectl",
                    "device",
                    "info",
                    "displays",
                    "-d",
                    self.udid,
                    "--json-output",
                    "-",
                ]
            )
        )
        displays = [d for d in data["result"]["displays"] if d.get("name", "").startswith("LCD")]
        active = next((d for d in displays if d.get("active")), None)
        if active is None:
            raise ValueError("No active Duo display reported; check the runtime")
        return {
            "hinge_angle": self.backend.angle(self.udid),
            "active_screen": "cover" if active.get("primary") else "inner",
            "display_id": active["displayId"],
            "rotation": active["currentOrientation"],
            "displays": displays,
        }

    def execute(
        self, angle: float | None = None, pose: str | None = None, orientation: str | None = None
    ) -> dict:
        """Apply one optional change and return observed state, including on timeout."""
        if sum(value is not None for value in (angle, pose, orientation)) > 1:
            raise ValueError("Choose only one of --angle, --pose or --orientation")
        target = POSES[pose] if pose is not None else angle
        if target is not None and (not math.isfinite(target) or not 0 <= target <= 180):
            raise ValueError("Angle must be between 0 and 180 degrees")
        if orientation is not None and orientation not in ROTATIONS:
            raise ValueError("Choose a supported orientation")
        self.validate_device()
        state = self.read()
        if target is not None:
            self.backend.hinge(self.udid, state["hinge_angle"], target)

        def matches() -> bool:
            """Check angle tolerance and endpoint display, or observed rotation."""
            if target is not None:
                screen = "cover" if target == 0 else "inner" if target == 180 else None
                return abs(state["hinge_angle"] - target) <= 2 and (
                    screen is None or state["active_screen"] == screen
                )
            return orientation is None or state["rotation"] == ROTATIONS[orientation]

        deadline = time.monotonic() + 5
        candidates = iter(("portrait", "landscape-left", "landscape-right", "pud"))
        while not matches() and time.monotonic() < deadline:
            if orientation is not None:
                candidate = next(candidates, None)
                if candidate is not None:
                    self.backend.orient(self.udid, candidate)
            time.sleep(0.2)
            state = self.read()
        result = {"success": matches(), "udid": self.udid, **state}
        if not result["success"]:
            result["error"] = (
                "Requested state not observed within five seconds; inspect state and retry"
            )
        return result


def main() -> None:
    """Expose concise and JSON modes without implicit device selection."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--udid", required=True, help="Explicit booted iPhone Duo UDID")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--state", action="store_true", help="Read state (default)")
    actions.add_argument("--angle", type=float, help="Hinge angle, 0–180 degrees")
    actions.add_argument("--pose", choices=POSES)
    actions.add_argument("--orientation", choices=ROTATIONS)
    parser.add_argument("--json", action="store_true", help="Full observed display state")
    parser.add_argument("--verbose", action="store_true", help="Full observed display state")
    args = parser.parse_args()
    try:
        result = DuoManager(args.udid).execute(args.angle, args.pose, args.orientation)
    except (RuntimeError, ValueError, KeyError, TypeError, OSError) as exc:
        result = {
            "success": False,
            "error": " ".join(str(exc).split()),
            "guidance": "Check Xcode, the runtime and the explicit booted Duo UDID",
        }
    if args.json or args.verbose:
        print(json.dumps(result, indent=2))
    elif "hinge_angle" in result:
        print(
            f"Duo: {result['hinge_angle']:g}° | {result['active_screen']} | "
            f"display {result['display_id']} | {result['rotation']}"
        )
        if not result["success"]:
            print(f"Error: {result['error']}")
        print("Capture with --display; inner-display coordinate touches are unverified")
    else:
        print(f"Error: {result['error']}; {result['guidance']}")
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
