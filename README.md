[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/conorluddy/ios-simulator-skill)

# iOS Simulator Skill for Claude Code

Production-ready skill for building, testing, and automating iOS apps. 27 scripts optimized for both human developers and AI agents.

## Xcode Build + Simulator Automation

This skill covers both sides of iOS development:

- **Xcode builds** via `xcodebuild` — compile, test, and parse results with progressive error disclosure
- **Simulator interaction** via `xcrun simctl` and `idb` — semantic UI navigation, accessibility testing, device lifecycle

If you only need Xcode build tooling without the simulator scripts, see the plugin version: [xclaude-plugin](https://github.com/conorluddy/xclaude-plugin)

## Installation

### Via Plugin Marketplace (Recommended)

In Claude Code:

```
/plugin marketplace add conorluddy/ios-simulator-skill
/plugin install ios-simulator-skill@conorluddy
```

### Via Git Clone

```bash
# Personal installation
git clone https://github.com/conorluddy/ios-simulator-skill.git ~/.claude/skills/ios-simulator-skill

# Project installation
git clone https://github.com/conorluddy/ios-simulator-skill.git .claude/skills/ios-simulator-skill
```

Restart Claude Code. The skill loads automatically.

### Prerequisites

- macOS 12+
- Xcode Command Line Tools (`xcode-select --install`)
- Python 3
- IDB (optional, for interactive features: `brew tap facebook/fb && brew install idb-companion`)
- Pillow (optional, for visual diffs: `pip3 install pillow`)

## Features

### Xcode Build with Progressive Disclosure

The `build_and_test.py` script wraps `xcodebuild` with token-efficient output. A build returns a single summary line with an xcresult ID:

```
Build: SUCCESS (0 errors, 3 warnings) [xcresult-20251018-143052]
```

Then drill into details on demand:

```bash
python scripts/build_and_test.py --get-errors xcresult-20251018-143052
python scripts/build_and_test.py --get-warnings xcresult-20251018-143052
python scripts/build_and_test.py --get-log xcresult-20251018-143052
```

This keeps agent conversations focused — no walls of build output unless you ask for them.

### Simulator Navigation via Accessibility

Instead of fragile pixel-coordinate tapping, all navigation uses iOS accessibility APIs to find elements by meaning:

```bash
# Fragile — breaks if UI changes
idb ui tap 320 400

# Robust — finds by meaning
python scripts/navigator.py --find-text "Login" --tap
```

The accessibility tree gives structured data (element types, labels, frames, tap targets) at ~10 tokens default output vs 1,600-6,300 tokens for a screenshot. See [AI-Accessible Apps](https://www.conor.fyi/writing/ai-access) for more on why accessibility-first navigation matters for AI agents.

### Screenshot Token Optimization

When screenshots are needed (visual verification, bug reports, diffs), the skill automatically resizes and compresses them to minimize token cost. Default output across all 27 scripts is 3-5 lines — 96% reduction vs raw tool output.

| Task | Raw Tools | This Skill | Savings |
|------|-----------|-----------|---------|
| Screen analysis | 200+ lines | 5 lines | 97.5% |
| Find & tap button | 100+ lines | 1 line | 99% |
| Login flow | 400+ lines | 15 lines | 96% |

### All 27 Scripts

Every script supports `--help` and `--json`. See **SKILL.md** for the complete reference.

#### Build & Development

| Script | What it does | Key flags |
|--------|-------------|-----------|
| `build_and_test.py` | Build Xcode projects, run tests, parse xcresult bundles | `--project`, `--scheme`, `--test`, `--get-errors`, `--get-warnings` |
| `log_monitor.py` | Real-time log monitoring with severity filtering | `--app`, `--severity`, `--follow`, `--duration` |

#### Device State

| Script | What it does | Key flags |
|--------|-------------|-----------|
| `appearance.py` | Switch dark mode, dynamic type, locale, region | `--theme`, `--text-size`, `--locale`, `--region`, `--reset` |
| `location.py` | Simulate GPS coordinates and run built-in scenarios | `--lat`, `--lng`, `--city`, `--gpx`, `--list-scenarios`, `--clear` |

#### Navigation & Interaction

| Script | What it does | Key flags |
|--------|-------------|-----------|
| `screen_mapper.py` | Analyze current screen, list interactive elements | `--verbose`, `--hints` |
| `navigator.py` | Find and interact with elements semantically | `--find-text`, `--find-type`, `--find-id`, `--tap`, `--enter-text` |
| `gesture.py` | Swipes, scrolls, pinches, long press, pull to refresh | `--swipe`, `--scroll`, `--pinch`, `--long-press`, `--refresh` |
| `keyboard.py` | Text input and hardware button control | `--type`, `--key`, `--button`, `--clear`, `--dismiss` |
| `app_launcher.py` | Launch, terminate, install, deep link apps | `--launch`, `--terminate`, `--install`, `--open-url`, `--list` |

#### Testing & Analysis

| Script | What it does | Key flags |
|--------|-------------|-----------|
| `accessibility_audit.py` | WCAG compliance checking on current screen | `--verbose`, `--output` |
| `visual_diff.py` | Compare two screenshots for visual changes | `--threshold`, `--output`, `--details` |
| `test_recorder.py` | Automated test documentation with screenshots | `--test-name`, `--output` |
| `app_state_capture.py` | Debugging snapshots (screenshot, hierarchy, logs) | `--app-bundle-id`, `--output`, `--log-lines` |
| `sim_health_check.sh` | Verify environment (Xcode, simctl, IDB, Python) | — |
| `model_inspector.py` | Inspect Core Data / SwiftData models from project files | `--project-path`, `--raw`, `--show-versions` |
| `container.py` | Inspect app sandbox: list, cat, UserDefaults, Core Data, export | `--ls`, `--cat`, `--userdefaults`, `--core-data-path`, `--export` |
| `hang_watcher.py` (HangBuster) | Record + summarise `os_log` hang events with progressive disclosure (session mode + raw NDJSON + legacy stream); auto-restart on stream death, automatic disk-cap cleanup | `--start [--raw-capture --max-size-mb N --no-gzip]`, `--stop`, `--get-details`, `--list-sessions`, `--diff`, `--budget-tokens`, `--auto-sample` (legacy: `--watch`, `--since`) |
| `localization_audit.py` | Audit `.xcstrings` catalogs for missing keys, unused keys, placeholder mismatches | `--catalog`, `--source`, `--strict` |

#### Permissions & Environment

| Script | What it does | Key flags |
|--------|-------------|-----------|
| `clipboard.py` | Copy text to simulator clipboard for paste testing | `--copy`, `--test-name` |
| `status_bar.py` | Override status bar (time, battery, network) | `--preset`, `--time`, `--battery-level`, `--clear` |
| `push_notification.py` | Send simulated push notifications | `--bundle-id`, `--title`, `--body`, `--payload` |
| `privacy_manager.py` | Grant, revoke, reset app permissions (13 services) | `--bundle-id`, `--grant`, `--revoke`, `--reset` |

#### Device Lifecycle

| Script | What it does | Key flags |
|--------|-------------|-----------|
| `simctl_boot.py` | Boot simulators with readiness verification | `--name`, `--wait-ready`, `--timeout`, `--all`, `--type` |
| `simctl_shutdown.py` | Gracefully shutdown simulators | `--name`, `--verify`, `--all`, `--type` |
| `simctl_create.py` | Create simulators by device type and OS version | `--device`, `--runtime`, `--list-devices` |
| `simctl_delete.py` | Delete simulators with safety confirmation | `--name`, `--yes`, `--all`, `--old` |
| `simctl_erase.py` | Factory reset without deletion | `--name`, `--verify`, `--all`, `--booted` |

## Configuration

Every operational limit — timeouts, output caps, polling intervals, cache size, post-action delays — is tunable via an `IOS_SIM_*` environment variable. Defaults are tuned for **local development on Apple Silicon**. Raise them on slow CI runners, large monorepos, or accessibility audits over complex screens. Lower them when you need faster failure or tighter token budgets.

There's a universal tradeoff to keep in mind:

- **Higher caps / longer timeouts** → fewer false failures, more complete diagnostics, **more tokens** consumed by AI agents and slower failures when something is genuinely broken.
- **Lower caps / shorter timeouts** → faster feedback, tighter token usage, **risk** of silently dropped errors or premature timeouts on legitimately slow operations.

### Boot & lifecycle timeouts

How long to wait on `xcrun simctl` operations.

| Variable | Default | Tradeoff |
|---|---|---|
| `IOS_SIM_BOOT_TIMEOUT` | `300` (s) | Wait for simulator readiness after `boot`. Lower → faster failure on broken sims. Higher → survives cold-start on slow CI runners (GitHub-hosted macOS can need 4–6 min). |
| `IOS_SIM_BOOT_SUBPROCESS_TIMEOUT` | `60` (s) | Timeout for the `simctl boot` call itself (before readiness polling starts). Rarely needs changing; bump only if you see `Boot command timed out` on resource-starved CI. |
| `IOS_SIM_ERASE_TIMEOUT` | `90` (s) | Wait for factory-reset verification. Larger simulators (lots of installed apps + data) can need more than the old 30s. |
| `IOS_SIM_POLL_INTERVAL` | `0.5` (s) | How often to re-check boot/erase state. Lower → more responsive (more CPU). Higher → quieter on slow CI but adds latency to “ready” detection. |
| `IOS_SIM_STATE_SUBPROCESS_TIMEOUT` | `15` (s) | Per-subprocess timeout in `app_state_capture.py`. Bump for apps with very large accessibility trees. |

### Build & test output caps

`build_and_test.py` returns counts by default and full details via xcresult ID; these caps govern what's surfaced in human/JSON output **before** progressive disclosure kicks in.

| Variable | Default | Tradeoff |
|---|---|---|
| `IOS_SIM_BUILD_SUMMARY_CAP` | `15` | Errors / failed tests in the default text summary. Lower → terser default output. Higher → less need to chase xcresult IDs for context. |
| `IOS_SIM_BUILD_VERBOSE_CAP` | `100` | Errors / warnings in `--verbose` mode. Mostly relevant for monorepos or first builds with many fixable warnings. |
| `IOS_SIM_BUILD_JSON_CAP` | `50` | Max errors / failed tests in `--json` output. Raise for CI dashboards that need exhaustive lists. |
| `IOS_SIM_BUILD_LOG_PREVIEW` | `4000` (chars) | Chars of build log included in default output. Higher → more context for failures, more tokens. |
| `IOS_SIM_BUILD_TIMEOUT` | `1800` (s) | Hard cap on a single `xcodebuild build` invocation. Default of 30 min covers most clean builds of large apps; raise for very large monorepos, lower to fail fast in CI when builds are expected to take seconds. Without this, a hung `xcodebuild` would block forever. |
| `IOS_SIM_TEST_TIMEOUT` | `2700` (s) | Hard cap on `xcodebuild test`. Tests can take significantly longer than builds (45 min default) because of simulator boot + animation delays. |
| `IOS_SIM_INTROSPECT_TIMEOUT` | `60` (s) | Timeout for `xcodebuild -list` and `xcrun simctl list` introspection calls. These should normally complete in &lt;1s; 60s catches Xcode-toolchain hangs without disrupting cold-start. |

### Log monitor output

`log_monitor.py` aggregates `os_log` output; these caps shape both the text summary and the structured JSON.

| Variable | Default | Tradeoff |
|---|---|---|
| `IOS_SIM_LOG_TEXT_SUMMARY` | `15` | Errors / warnings shown in the text summary. The default surfaces enough for most debugging without flooding terminal output. |
| `IOS_SIM_LOG_LINE_MAX` | `300` (chars) | Per-line truncation. Crash messages with full Swift symbol mangling can exceed 200 chars; raise if you see “…” cutting off the actionable bit. |
| `IOS_SIM_LOG_TAIL` | `200` (lines) | Recent log lines shown in verbose mode and JSON `sample_logs`. Also used by xcode log excerpt. Lower for tighter context, higher for richer post-mortems. |
| `IOS_SIM_LOG_JSON_CAP` | `100` | Max errors / warnings in JSON output. Raise if you're piping into a dashboard that needs the full picture. |
| `IOS_SIM_HANG_PREDICATE` | _(default)_ | Override the `os_log` predicate used by `hang_watcher.py`. The default catches RunningBoard watchdog kills, explicit "Hang detected" messages, and main-thread hang annotations. Hang events originate from system daemons (RunningBoard, SpringBoard, watchdog) — *not* the target app's process — so the predicate intentionally stays simulator-global. `--bundle-id` is applied post-parse against the event payload, never ANDed into the predicate. |
| `IOS_SIM_HANG_MIN_MS` | `250` | HangBuster threshold: events below this duration never reach disk. |
| `IOS_SIM_HANG_SESSION_TTL_HOURS` | `24` | HangBuster session prune age. Pruning runs on every `--start`. |
| `IOS_SIM_HANG_DEFAULT_TOP_N` | `3` | Default top-N clusters in `--stop` L1 output. |
| `IOS_SIM_HANG_BUDGET_TOKENS` | _(unset)_ | Default token budget for `--stop` (picks L0/L1/L2 to fit). |
| `IOS_SIM_HANG_MAX_RESTARTS` | `3` | HangBuster worker: bounded `log stream` respawn attempts on EOF/subprocess death before the session is marked `crashed`. Set to `0` to disable auto-restart. |
| `IOS_SIM_HANG_TOTAL_CAP_MB` | `100` | HangBuster aggregate disk cap. When total session-state exceeds this on `--start`, oldest sessions are dropped first. Set to `0` to disable. |

### UI navigation & screen mapping

These shape what AI agents see when exploring a screen. They're the biggest direct lever on token consumption per navigation step.

| Variable | Default | Tradeoff |
|---|---|---|
| `IOS_SIM_MAX_ELEMENTS` | `25` | Tappable elements listed by `navigator.py`. Default is enough for most screens; raise to `100+` for dense Settings-style screens or audit workflows. **High token impact** at high values. |
| `IOS_SIM_SCREEN_BUTTONS_PREVIEW` | `15` | Button names in `screen_mapper.py` summary. |
| `IOS_SIM_SCREEN_SECTION_ITEMS` | `10` | Items per section in `screen_mapper.py` summary. |
| `IOS_SIM_APPS_PREVIEW` | `30` | Installed apps listed by `app_launcher.py` before truncation. |
| `IOS_SIM_TAP_SETTLE_MS` | `500` (ms) | Delay after a tap before reading new state. Lower → faster navigation on snappy apps. Higher → safer on apps with heavy animations or async loading; raises end-to-end test runtime linearly. |
| `IOS_SIM_RELAUNCH_DELAY_MS` | `1000` (ms) | Delay between terminate and re-launch in `app_launcher.py --restart`. Raise if you see relaunches catching the previous process still tearing down. |

### Accessibility audit

| Variable | Default | Tradeoff |
|---|---|---|
| `IOS_SIM_A11Y_TOP_ISSUES` | `10` | Top issues surfaced per audit. Default of 3 in older versions was almost always too aggressive for real-world apps. Raise for first-pass audits, lower for regression checks. |
| `IOS_SIM_A11Y_LABEL_MAX` | `80` (chars) | Max chars of `AXLabel` retained in audit output. Custom localized labels often exceed 30 chars; 80 catches almost all. |

### Progressive disclosure cache

`ProgressiveCache` stores large outputs (build results, log dumps) keyed by short IDs so the default output stays minimal.

| Variable | Default | Tradeoff |
|---|---|---|
| `IOS_SIM_CACHE_TTL_HOURS` | `1` | How long cache entries remain valid. Lower → fresher data on next retrieve, more re-runs. Higher → faster reruns in long CI pipelines, risk of stale results if simulator state changed. |
| `IOS_SIM_CACHE_MAX_ENTRIES` | `500` | Hard cap; oldest entries (by mtime) are evicted on every `save()`. Prevents unbounded growth of `~/.ios-simulator-skill/cache/` in long-running environments. Raise only if you frequently need to retrieve entries older than ~500 saves. |

### Examples

```bash
# Slow GitHub Actions macOS runner — give boot up to 10 minutes
IOS_SIM_BOOT_TIMEOUT=600 python scripts/simctl_boot.py --wait-ready

# Monorepo with hundreds of warnings — see them all in verbose mode
IOS_SIM_BUILD_VERBOSE_CAP=500 python scripts/build_and_test.py --verbose

# Complex Settings-style screen — return more tappable elements
IOS_SIM_MAX_ELEMENTS=100 python scripts/navigator.py --list-tappable

# Snappy app — cut tap-settle delay in half for faster E2E runs
IOS_SIM_TAP_SETTLE_MS=250 python scripts/navigator.py --find-text "Login" --tap

# Long CI pipeline — keep cache entries valid for the whole job
IOS_SIM_CACHE_TTL_HOURS=8 python scripts/build_and_test.py --project MyApp.xcodeproj
```

You can also export the vars once for the whole session:

```bash
export IOS_SIM_BOOT_TIMEOUT=600
export IOS_SIM_LOG_TAIL=500
export IOS_SIM_MAX_ELEMENTS=50
# … all subsequent scripts honor them
```

Parse errors fall back to the documented default with a warning on stderr — no scripts will crash on a malformed env var.

## Evaluation

Tested using [Claude Code evals](https://docs.claude.com/en/docs/claude-code/evals):

| Condition | Pass Rate |
|-----------|-----------|
| With skill | **100%** (3/3) |
| Without skill | **46%** (~1.4/3) |

```bash
claude evals run evals/evals.json --skill ios-simulator-skill
```

## License

MIT
