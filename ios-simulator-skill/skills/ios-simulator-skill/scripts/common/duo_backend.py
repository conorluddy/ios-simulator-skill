"""Experimental private Duo backend, isolated for replacement by supported APIs."""

import hashlib
import math
import os
import platform
import subprocess
import tempfile
from pathlib import Path


def command(args: list[str]) -> str:
    """Run a bounded command and surface a concise actionable failure."""
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=15, check=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or f"exit {exc.returncode}").strip().splitlines()
        raise RuntimeError(
            f"{args[0]} failed: {(detail[-1] if detail else f"exit {exc.returncode}")}"
        ) from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"{args[0]} unavailable or timed out; check the selected Xcode") from exc
    return result.stdout


class DuoBackend:
    """Compile and invoke the bundled simulator helper with the selected toolchain."""

    def __init__(self) -> None:
        """Defer compilation until a valid Duo is selected."""
        self.binary: Path | None = None

    def compile(self) -> Path:
        """Cache a signed helper keyed by source, toolchain, SDK and architecture."""
        source = Path(__file__).resolve().parents[1] / "native" / "duo.m"
        identity = source.read_bytes() + platform.machine().encode()
        for args in (
            ["xcodebuild", "-version"],
            ["--sdk", "iphonesimulator", "--show-sdk-path"],
            ["--sdk", "iphonesimulator", "--find", "clang"],
        ):
            identity += command(["xcrun", *args]).encode()
        directory = (
            Path.home()
            / "Library/Caches/ios-simulator-skill/duo"
            / hashlib.sha256(identity).hexdigest()
        )
        binary = directory / "duo"
        if os.access(binary, os.X_OK):
            return binary
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="build-", dir=directory) as temporary:
            output = Path(temporary) / "duo"
            command(
                [
                    "xcrun",
                    "--sdk",
                    "iphonesimulator",
                    "clang",
                    "-fobjc-arc",
                    "-O2",
                    "-arch",
                    "arm64" if platform.machine() == "arm64" else "x86_64",
                    "-mios-simulator-version-min=17.0",
                    "-framework",
                    "Foundation",
                    "-framework",
                    "IOKit",
                    "-framework",
                    "CoreMotion",
                    str(source),
                    "-o",
                    str(output),
                ]
            )
            command(["codesign", "-f", "-s", "-", str(output)])
            output.replace(binary)
        return binary

    def invoke(self, udid: str, *args: str) -> str:
        """Run the helper inside the explicitly selected simulator."""
        if self.binary is None:
            self.binary = self.compile()
        return command(["xcrun", "simctl", "spawn", udid, str(self.binary), *args])

    def angle(self, udid: str) -> float:
        """Read an observed hinge angle, rejecting invalid native output."""
        value = float(self.invoke(udid, "read").strip())
        if not math.isfinite(value) or not 0 <= value <= 180:
            raise ValueError("Invalid hinge readback; check the Duo runtime")
        return value

    def hinge(self, udid: str, initial: float, target: float) -> None:
        """Dispatch a continuous hinge transition; caller must verify readback."""
        self.invoke(udid, "hinge", str(initial), str(target))

    def orient(self, udid: str, orientation: str) -> None:
        """Dispatch an orientation candidate; caller must verify readback."""
        self.invoke(udid, "orientation", orientation)
