---
name: ios-simulator-skill
version: 1.5.0
description: 22 production-ready scripts for iOS app testing, building, and automation. Provides semantic UI navigation, build automation, accessibility testing, and simulator lifecycle management. Optimized for AI agents with minimal token output.
---

# iOS Simulator Skill

Build, test, and automate iOS applications using accessibility-driven navigation and structured data instead of pixel coordinates.

## Quick Start

```bash
# 1. Check environment
bash scripts/sim_health_check.sh

# 2. Launch app
python scripts/app_launcher.py --launch com.example.app

# 3. Map screen to see elements
python scripts/screen_mapper.py

# 4. Tap button
python scripts/navigator.py --find-text "Login" --tap

# 5. Enter text
python scripts/navigator.py --find-type TextField --enter-text "user@example.com"
```

All scripts support `--help` for detailed options and `--json` for machine-readable output.

## Navigation Strategy

**Always prefer the accessibility tree over screenshots for navigation.** The accessibility tree gives you element types, labels, frames, and tap targets — structured data that's cheaper and more reliable than image analysis.

Use this priority:
1. `screen_mapper.py` → structured element list (5-7 lines, ~10 tokens)
2. `navigator.py --find-text/--find-type/--find-id` → semantic interaction
3. Screenshots → only for visual verification, bug reports, or visual diff

Screenshots cost 1,600–6,300 tokens depending on size. The accessibility tree costs 10–50 tokens in default mode.

## 22 Production Scripts

### Build & Development (2 scripts)

1. **build_and_test.py** - Build Xcode projects, run tests, parse results with progressive disclosure
   - Build with live result streaming
   - Parse errors and warnings from xcresult bundles
   - Retrieve detailed build logs on demand
   - Options: `--project`, `--scheme`, `--clean`, `--test`, `--verbose`, `--json`

2. **log_monitor.py** - Real-time log monitoring with intelligent filtering
   - Stream logs or capture by duration
   - Filter by severity (error/warning/info/debug)
   - Deduplicate repeated messages
   - Options: `--app`, `--severity`, `--follow`, `--duration`, `--output`, `--json`

### Navigation & Interaction (5 scripts)

3. **screen_mapper.py** - Analyze current screen and list interactive elements
   - Element type breakdown
   - Interactive button list
   - Text field status
   - Options: `--verbose`, `--hints`, `--json`

4. **navigator.py** - Find and interact with elements semantically
   - Find by text (fuzzy matching)
   - Find by element type
   - Find by accessibility ID
   - Enter text or tap elements
   - Options: `--find-text`, `--find-type`, `--find-id`, `--tap`, `--enter-text`, `--json`

5. **gesture.py** - Perform swipes, scrolls, pinches, and complex gestures
   - Directional swipes (up/down/left/right)
   - Multi-swipe scrolling
   - Pinch zoom
   - Long press
   - Pull to refresh
   - Options: `--swipe`, `--scroll`, `--pinch`, `--long-press`, `--refresh`, `--json`

6. **keyboard.py** - Text input and hardware button control
   - Type text (fast or slow)
   - Special keys (return, delete, tab, space, arrows)
   - Hardware buttons (home, lock, volume, screenshot)
   - Key combinations
   - Options: `--type`, `--key`, `--button`, `--slow`, `--clear`, `--dismiss`, `--json`

7. **app_launcher.py** - App lifecycle management
   - Launch apps by bundle ID
   - Terminate apps
   - Install/uninstall from .app bundles
   - Deep link navigation
   - List installed apps
   - Check app state
   - Options: `--launch`, `--terminate`, `--install`, `--uninstall`, `--open-url`, `--list`, `--state`, `--json`

### Testing & Analysis (6 scripts)

8. **accessibility_audit.py** - Check WCAG compliance on current screen
   - Critical issues (missing labels, empty buttons, no alt text)
   - Warnings (missing hints, small touch targets)
   - Info (missing IDs, deep nesting)
   - Options: `--verbose`, `--output`, `--json`

9. **visual_diff.py** - Compare two screenshots for visual changes
   - Pixel-by-pixel comparison
   - Threshold-based pass/fail
   - Generate diff images
   - Options: `--threshold`, `--output`, `--details`, `--json`

10. **test_recorder.py** - Automatically document test execution
    - Capture screenshots and accessibility trees per step
    - Generate markdown reports with timing data
    - Options: `--test-name`, `--output`, `--verbose`, `--json`

11. **app_state_capture.py** - Create comprehensive debugging snapshots
    - Screenshot, UI hierarchy, app logs, device info
    - Markdown summary for bug reports
    - Options: `--app-bundle-id`, `--output`, `--log-lines`, `--json`

12. **sim_health_check.sh** - Verify environment is properly configured
    - Check macOS, Xcode, simctl, IDB, Python
    - List available and booted simulators
    - Verify Python packages (Pillow)

13. **model_inspector.py** - Inspect Core Data and SwiftData models from project files
    - Parse .xcdatamodeld packages (entities, attributes, relationships)
    - Detect model versions and current active version
    - Best-effort SwiftData @Model class extraction
    - Raw source dump for any model on demand (`--raw ModelName`)
    - Options: `--project-path`, `--core-data-only`, `--swiftdata-only`, `--show-versions`, `--raw`, `--verbose`, `--json`

### Advanced Testing & Permissions (4 scripts)

14. **clipboard.py** - Manage simulator clipboard for paste testing
    - Copy text to clipboard
    - Test paste flows without manual entry
    - Options: `--copy`, `--test-name`, `--expected`, `--json`

15. **status_bar.py** - Override simulator status bar appearance
    - Presets: clean (9:41, 100% battery), testing (11:11, 50%), low-battery (20%), airplane (offline)
    - Custom time, network, battery, WiFi settings
    - Options: `--preset`, `--time`, `--data-network`, `--battery-level`, `--clear`, `--json`

16. **push_notification.py** - Send simulated push notifications
    - Simple mode (title + body + badge)
    - Custom JSON payloads
    - Test notification handling and deep links
    - Options: `--bundle-id`, `--title`, `--body`, `--badge`, `--payload`, `--json`

17. **privacy_manager.py** - Grant, revoke, and reset app permissions
    - 13 supported services (camera, microphone, location, contacts, photos, calendar, health, etc.)
    - Batch operations (comma-separated services)
    - Audit trail with test scenario tracking
    - Options: `--bundle-id`, `--grant`, `--revoke`, `--reset`, `--list`, `--json`

### Device Lifecycle Management (5 scripts)

18. **simctl_boot.py** - Boot simulators with optional readiness verification
    - Boot by UDID or device name
    - Wait for device ready with timeout
    - Batch boot operations (--all, --type)
    - Performance timing
    - Options: `--udid`, `--name`, `--wait-ready`, `--timeout`, `--all`, `--type`, `--json`

19. **simctl_shutdown.py** - Gracefully shutdown simulators
    - Shutdown by UDID or device name
    - Optional verification of shutdown completion
    - Batch shutdown operations
    - Options: `--udid`, `--name`, `--verify`, `--timeout`, `--all`, `--type`, `--json`

20. **simctl_create.py** - Create simulators dynamically
    - Create by device type and iOS version
    - List available device types and runtimes
    - Custom device naming
    - Returns UDID for CI/CD integration
    - Options: `--device`, `--runtime`, `--name`, `--list-devices`, `--list-runtimes`, `--json`

21. **simctl_delete.py** - Permanently delete simulators
    - Delete by UDID or device name
    - Safety confirmation by default (skip with --yes)
    - Batch delete operations
    - Smart deletion (--old N to keep N per device type)
    - Options: `--udid`, `--name`, `--yes`, `--all`, `--type`, `--old`, `--json`

22. **simctl_erase.py** - Factory reset simulators without deletion
    - Preserve device UUID (faster than delete+create)
    - Erase all, by type, or booted simulators
    - Optional verification
    - Options: `--udid`, `--name`, `--verify`, `--timeout`, `--all`, `--type`, `--booted`, `--json`

## Common Patterns

**Auto-UDID Detection**: Most scripts auto-detect the booted simulator if --udid is not provided.

**Device Name Resolution**: Use device names (e.g., "iPhone 16 Pro") instead of UDIDs - scripts resolve automatically.

**Batch Operations**: Many scripts support `--all` for all simulators or `--type iPhone` for device type filtering.

**Output Formats**: Default is concise human-readable output. Use `--json` for machine-readable output in CI/CD.

**Help**: All scripts support `--help` for detailed options and examples.

**Screenshot Sizing**: Screenshots are resized to save tokens. Presets: `full` (3-4 tiles, ~5K tokens), `half` (1 tile, ~1.6K tokens, default), `quarter` (1 tile, ~800 tokens, less detail). Use `quarter` for quick visual checks, `half` for readable UI, `full` only when pixel-level detail matters. Scripts that capture screenshots (`app_state_capture.py`, `test_recorder.py`) default to `half`.

## Typical Workflow

1. Verify environment: `bash scripts/sim_health_check.sh`
2. Launch app: `python scripts/app_launcher.py --launch com.example.app`
3. Analyze screen: `python scripts/screen_mapper.py`
4. Interact: `python scripts/navigator.py --find-text "Button" --tap`
5. Verify: `python scripts/accessibility_audit.py`
6. Debug if needed: `python scripts/app_state_capture.py --app-bundle-id com.example.app`

## Configuration

Most operational limits can be tuned via environment variables. Defaults work for typical local development; raise them for slow CI runners, large monorepo builds, or accessibility audits on complex screens.

| Variable | Default | Controls |
|---|---|---|
| `IOS_SIM_A11Y_LABEL_MAX` | `80` | Max chars of `AXLabel` retained in accessibility audit output |
| `IOS_SIM_A11Y_TOP_ISSUES` | `10` | Top accessibility issues surfaced per audit |
| `IOS_SIM_APPS_PREVIEW` | `30` | App entries listed by `app_launcher.py` before truncation |
| `IOS_SIM_BOOT_SUBPROCESS_TIMEOUT` | `60` | Timeout for the `simctl boot` subprocess itself (seconds) |
| `IOS_SIM_BOOT_TIMEOUT` | `300` | Wait-for-ready timeout after boot (seconds) |
| `IOS_SIM_BUILD_JSON_CAP` | `50` | Max build errors / failed tests in JSON output |
| `IOS_SIM_BUILD_LOG_PREVIEW` | `4000` | Chars of build log preview in default output |
| `IOS_SIM_BUILD_TIMEOUT` | `1800` | Max seconds for an `xcodebuild build` invocation before kill |
| `IOS_SIM_INTROSPECT_TIMEOUT` | `60` | Timeout for `xcodebuild -list` and `simctl list` lookups (seconds) |
| `IOS_SIM_TEST_TIMEOUT` | `2700` | Max seconds for an `xcodebuild test` invocation before kill |
| `IOS_SIM_BUILD_SUMMARY_CAP` | `15` | Errors/failures in default build summary |
| `IOS_SIM_BUILD_VERBOSE_CAP` | `100` | Errors/warnings in verbose build output |
| `IOS_SIM_CACHE_MAX_ENTRIES` | `500` | Max entries in progressive disclosure cache (LRU eviction) |
| `IOS_SIM_CACHE_TTL_HOURS` | `1` | Cache entry expiration |
| `IOS_SIM_ERASE_TIMEOUT` | `90` | Wait-for-erase timeout (seconds) |
| `IOS_SIM_LOG_JSON_CAP` | `100` | Max errors/warnings in `log_monitor.py` JSON output |
| `IOS_SIM_LOG_LINE_MAX` | `300` | Per-line truncation in log summaries |
| `IOS_SIM_LOG_TAIL` | `200` | Lines of log tail in verbose / sample output |
| `IOS_SIM_LOG_TEXT_SUMMARY` | `15` | Errors/warnings shown in text-mode log summary |
| `IOS_SIM_MAX_ELEMENTS` | `25` | Tappable elements listed by `navigator.py` |
| `IOS_SIM_POLL_INTERVAL` | `0.5` | Boot/erase state polling interval (seconds) |
| `IOS_SIM_RELAUNCH_DELAY_MS` | `1000` | Delay between terminate and re-launch in `app_launcher.py` |
| `IOS_SIM_SCREEN_BUTTONS_PREVIEW` | `15` | Button names listed by `screen_mapper.py` |
| `IOS_SIM_SCREEN_SECTION_ITEMS` | `10` | Items per section shown by `screen_mapper.py` |
| `IOS_SIM_STATE_SUBPROCESS_TIMEOUT` | `15` | Subprocess timeout in `app_state_capture.py` (seconds) |
| `IOS_SIM_TAP_SETTLE_MS` | `500` | Post-tap settle delay in `navigator.py` |

Example:

```bash
# Slow GitHub Actions runner: give boot 10 minutes
IOS_SIM_BOOT_TIMEOUT=600 python scripts/simctl_boot.py --wait-ready
```

## Requirements

- macOS 12+
- Xcode Command Line Tools
- Python 3
- IDB (optional, for interactive features)

## Documentation

- **SKILL.md** (this file) - Script reference and quick start
- **README.md** - Installation and examples
- **CLAUDE.md** - Architecture and implementation details
- **references/** - Deep documentation on specific topics
- **examples/** - Complete automation workflows

## Key Design Principles

**Semantic Navigation**: Find elements by meaning (text, type, ID) not pixel coordinates. Survives UI changes.

**Token Efficiency**: Concise default output (3-5 lines) with optional verbose and JSON modes for detailed results.

**Accessibility-First**: Built on standard accessibility APIs for reliability and compatibility.

**Zero Configuration**: Works immediately on any macOS with Xcode. No setup required.

**Structured Data**: Scripts output JSON or formatted text, not raw logs. Easy to parse and integrate.

**Auto-Learning**: Build system remembers your device preference. Configuration stored per-project.

---

Use these scripts directly or let Claude Code invoke them automatically when your request matches the skill description.
