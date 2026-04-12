[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/conorluddy/ios-simulator-skill)

# iOS Simulator Skill for Claude Code

Production-ready skill for building, testing, and automating iOS apps. 22 scripts optimized for both human developers and AI agents.

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

When screenshots are needed (visual verification, bug reports, diffs), the skill automatically resizes and compresses them to minimize token cost. Default output across all 22 scripts is 3-5 lines — 96% reduction vs raw tool output.

| Task | Raw Tools | This Skill | Savings |
|------|-----------|-----------|---------|
| Screen analysis | 200+ lines | 5 lines | 97.5% |
| Find & tap button | 100+ lines | 1 line | 99% |
| Login flow | 400+ lines | 15 lines | 96% |

### All 22 Scripts

Every script supports `--help` and `--json`. See **SKILL.md** for the complete reference.

#### Build & Development

| Script | What it does | Key flags |
|--------|-------------|-----------|
| `build_and_test.py` | Build Xcode projects, run tests, parse xcresult bundles | `--project`, `--scheme`, `--test`, `--get-errors`, `--get-warnings` |
| `log_monitor.py` | Real-time log monitoring with severity filtering | `--app`, `--severity`, `--follow`, `--duration` |

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
