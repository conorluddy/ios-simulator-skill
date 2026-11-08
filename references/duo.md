# Duo controls and display capture

Ported from [xc-mcp PR #155](https://github.com/conorluddy/xc-mcp/pull/155), source
revision `9bd800db58d2a44438c28bd7074723ec0cd40bfb`. The npm release changes are excluded.

Run these paths relative to `ios-simulator-skill/skills/ios-simulator-skill/`:

```bash
python3 scripts/duo.py --udid <BOOTED_DUO_UDID> --state --json
python3 scripts/duo.py --udid <BOOTED_DUO_UDID> --pose open
python3 scripts/duo.py --udid <BOOTED_DUO_UDID> --angle 127
python3 scripts/duo.py --udid <BOOTED_DUO_UDID> --orientation landscape
python3 scripts/app_state_capture.py --udid <BOOTED_DUO_UDID> --display 3 --output duo-state
```

`--pose closed|partial|open` means 0°/90°/180°. `--angle` accepts any finite number
between 0 and 180. `--orientation` accepts portrait, landscape, portrait-upside-down,
or landscape-flipped. Choose one action; no action reads state. Unlike general simulator
scripts, this experimental device-specific command requires an explicit booted Duo UDID.
Device identity is checked before any helper compilation or dispatch.

Changes succeed only when readback matches. Hinge tolerance is two degrees; closed and
open also require the cover and inner display respectively. Intermediate angles make no
promise about which screen is active. Rotation tries native orientation candidates and
checks the observed interface rotation, rather than assuming sensor direction maps directly
to interface direction. Timeout results include the last observed state and exit 1.
The five-second polling budget starts after initial reads and hinge dispatch; each external
command separately times out after 15 seconds, so total duration can exceed five seconds.

## Backend and distribution

The bundled `scripts/native/duo.m` reads `CMAngleManager` and sends private simulator HID
hinge/orientation events. It credits the mechanism research in
[hinge](https://github.com/artemnovichkov/hinge) and
[duoctl](https://github.com/skarol/duoctl). No separate community CLI is required.
`common/duo_backend.py` compiles and ad-hoc signs it with the selected Xcode on first use,
caching under `~/Library/Caches/ios-simulator-skill/duo/`. The cache key includes source,
Xcode version, SDK path, compiler path and host architecture. Temporary build directories
are unique and publication uses an atomic rename. Both source and Python backend live
inside the distributed skill, so the existing zip workflow includes them.

These private interfaces are experimental. Replace folding and rotation independently
when supported headless APIs provide equivalent state control and observed readback.
XCTest-only hinge methods do not meet that requirement.

## Capture contract

`app_state_capture.py` and `test_recorder.py` accept `--display` in file and inline modes.
Use the observed `display_id` from Duo state; IDs 1 and 3 were observed locally but are
not assumed by the implementation. The shared capture helper passes `--display=<ID>`
to simctl and returns display metadata, using isolated temporary files with cleanup on
failure. Unknown image dimensions are zero rather than guessed when Pillow is absent.

Accessibility trees are captured independently. No coordinate transform or inner-display
idb touch routing is claimed. An inactive display may produce a black frame. This package
has no video capture command, so the source PR's video display selection is excluded.

## Live verification — 2026-11-08

Xcode 27.1 / iOS 27.1, existing iPhone Duo
`DD124D1F-540F-453D-BCBB-602F0854D2B6`:

- Bundled helper compiled, signed and executed successfully.
- Observed 0°, 90°, 127° and 180°; endpoints activated cover display 1 and inner display 3.
- Explicit file captures of both active displays were non-black: cover 1398×2034,
  inner 2853×2007 in landscape.
- All four inner orientations passed with one-second pauses between requests.
- Explicit inline inner capture passed at quarter size (713×501).
- Cover landscape, upside-down and flipped requests timed out with observed `rot0`,
  returning failure. Cover portrait passed. Rotation depends on runtime/app support.

The simulator was restored to closed portrait and returned to its original shutdown state.

Other Xcode/runtime versions and inner-display coordinate touches were not verified.
