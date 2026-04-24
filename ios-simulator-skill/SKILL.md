---
name: ios-simulator-skill
version: 1.5.0
description: Build, test, and drive iOS apps on the simulator. Wraps xcodebuild, xcrun simctl, and idb with token-efficient scripts for semantic UI navigation, progressive build output, a11y audits, and simulator lifecycle. Use when working with Xcode projects, .swift/.m/.h files, or anything involving the iOS simulator.
when_to_use: Activate for iOS/macOS app work — building Xcode projects, running XCTest, interacting with the iOS simulator (tap, type, gesture, screenshot), inspecting Core Data/SwiftData models, auditing accessibility, or managing simulator devices. Trigger phrases include "build the app", "run the tests", "tap the login button", "screenshot the simulator", "why is the build failing", "boot a simulator".
paths: "**/*.xcodeproj/**, **/*.xcworkspace/**, **/Package.swift, **/*.swift, **/*.m, **/*.h, **/*.xcdatamodeld/**"
allowed-tools: Bash(python3 *) Bash(python *) Bash(xcrun *) Bash(xcodebuild *) Bash(idb *) Bash(bash *)
---

# iOS Simulator Skill

## Live environment

- Booted simulators: !`xcrun simctl list devices booted 2>/dev/null | grep -E "^\s+\w" || echo "  (none booted)"`
- Xcode: !`xcodebuild -version 2>/dev/null | head -1 || echo "not installed"`
- IDB: !`command -v idb >/dev/null && idb --version 2>/dev/null || echo "not installed (interactive UI features disabled)"`

## How to invoke scripts

All scripts live under `${CLAUDE_SKILL_DIR}/scripts/`. **Always use the full path** — your working directory is the user's project, not this skill. Example:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/screen_mapper.py
python3 ${CLAUDE_SKILL_DIR}/scripts/navigator.py --find-text "Login" --tap
```

Every script supports `--help` (detailed flags) and `--json` (machine-readable output). For the full flag reference, read [reference.md](reference.md) on demand.

## Core rule: structure over pixels

**Prefer the accessibility tree over screenshots.** A screenshot costs 1,600–6,300 tokens; an a11y element list costs 10–50. Use screenshots only for visual verification, bug reports, or `visual_diff`.

Navigation priority:
1. `screen_mapper.py` — list what's on screen (structured, ~10 tokens)
2. `navigator.py --find-text/--find-type/--find-id` — interact semantically
3. `gesture.py` / `keyboard.py` — swipes, scrolls, typing
4. Screenshot — only when visual state is the question

## Workflows

### Build an Xcode project

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/build_and_test.py --project MyApp.xcodeproj --scheme MyApp
```

Returns one line with an `xcresult-ID`. On failure, drill in:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/build_and_test.py --get-errors xcresult-<ID>
python3 ${CLAUDE_SKILL_DIR}/scripts/build_and_test.py --get-warnings xcresult-<ID>
python3 ${CLAUDE_SKILL_DIR}/scripts/build_and_test.py --get-log xcresult-<ID>   # last resort
```

Do **not** dump full `xcodebuild` output into context — use progressive disclosure.

### Run a failing test and debug it

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/debug_failing_test.py \
    --project MyApp.xcodeproj --scheme MyApp \
    --test MyAppTests/LoginTests/testInvalidPassword \
    --bundle-id com.example.MyApp
```

Runs the test, and on failure captures xcresult errors + app logs + UI hierarchy + screenshot into a timestamped bundle. Returns a one-line summary with the bundle path.

### Launch and drive an app

```bash
# 1. Launch
python3 ${CLAUDE_SKILL_DIR}/scripts/app_launcher.py --launch com.example.MyApp

# 2. See what's on screen
python3 ${CLAUDE_SKILL_DIR}/scripts/screen_mapper.py

# 3. Interact semantically
python3 ${CLAUDE_SKILL_DIR}/scripts/navigator.py --find-type TextField --enter-text "user@example.com"
python3 ${CLAUDE_SKILL_DIR}/scripts/navigator.py --find-text "Sign In" --tap

# 4. Verify
python3 ${CLAUDE_SKILL_DIR}/scripts/accessibility_audit.py
```

### Simulator lifecycle

Auto-detects the booted sim when `--udid` is omitted. Resolve by device name ("iPhone 16 Pro") — UDIDs are rarely needed.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/simctl_boot.py --name "iPhone 16 Pro" --wait-ready
python3 ${CLAUDE_SKILL_DIR}/scripts/simctl_erase.py --booted      # fast reset
python3 ${CLAUDE_SKILL_DIR}/scripts/simctl_shutdown.py --all
```

## Script index

Read [reference.md](reference.md) for all flags. These are the scripts available under `${CLAUDE_SKILL_DIR}/scripts/`:

| Area | Scripts |
|------|---------|
| Build & logs | `build_and_test.py`, `log_monitor.py` |
| UI navigation | `screen_mapper.py`, `navigator.py`, `gesture.py`, `keyboard.py`, `app_launcher.py` |
| Testing & debug | `debug_failing_test.py`, `accessibility_audit.py`, `visual_diff.py`, `test_recorder.py`, `app_state_capture.py`, `model_inspector.py`, `sim_health_check.sh` |
| Env & permissions | `clipboard.py`, `status_bar.py`, `push_notification.py`, `privacy_manager.py` |
| Device lifecycle | `simctl_boot.py`, `simctl_shutdown.py`, `simctl_create.py`, `simctl_delete.py`, `simctl_erase.py` |

## Conventions

- **UDID is optional.** Scripts auto-detect the booted simulator. Pass `--name "iPhone 16 Pro"` or `--udid` only when multiple sims are booted.
- **Output is terse by default.** Add `--verbose` for human detail or `--json` for parsing.
- **Screenshots auto-resize.** Default is `half` (~1.6K tokens). Use `quarter` for quick checks, `full` only when pixel detail matters.
- **xcresult bundles persist.** Reference them by ID across calls within a session.
- **No `idb`? Navigation and gestures are unavailable.** Build, logs, simctl, and model inspection still work. Tell the user to `brew install idb-companion` if they need UI automation.

## When things go wrong

- **"No booted device"** → `simctl_boot.py --name "iPhone 16 Pro" --wait-ready`
- **Element not found** → run `screen_mapper.py --verbose` to see the full tree; the label may not match what the user said
- **Build fails with signing error** → `build_and_test.py --get-errors <id>`; signing issues usually need user intervention, don't auto-retry
- **Tap does nothing** → element may be occluded or offscreen; try `gesture.py --scroll down` then re-map
- **Stale UI state** → `app_launcher.py --terminate <bundle>` then relaunch

## Additional resources

- [reference.md](reference.md) — full flag reference for every script
- `scripts/*.py --help` — authoritative per-script docs
