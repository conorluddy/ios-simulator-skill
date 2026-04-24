<div align="center">

# 📱 iOS Simulator Skill for Claude Code

### Give Claude reliable hands on iOS.

**Build Xcode projects, drive the simulator semantically, and ship features —**
**all from inside a Claude Code conversation, in a fraction of the tokens.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE.md)
[![Python](https://img.shields.io/badge/Python-3.12+-3776ab.svg?logo=python&logoColor=white)](https://www.python.org)
[![macOS](https://img.shields.io/badge/macOS-12+-black.svg?logo=apple)](https://developer.apple.com)
[![Claude Code](https://img.shields.io/badge/Claude_Code-Skill-D97757.svg)](https://code.claude.com/docs/en/skills)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/conorluddy/ios-simulator-skill)

[**Install**](#-install) · [**Quick Start**](#-quick-start) · [**Scripts**](#-scripts-at-a-glance) · [**Why**](#-why-it-works) · [**SKILL.md**](ios-simulator-skill/SKILL.md)

</div>

---

## 🚀 What it does

Without this skill, Claude pokes at the iOS simulator with pixel coordinates and dumps walls of `xcodebuild` output into context. With it, Claude does **real iOS work** in a few turns:

```bash
$ python3 ${CLAUDE_SKILL_DIR}/scripts/build_and_test.py --project MyApp.xcodeproj --scheme MyApp
Build: SUCCESS (0 errors, 3 warnings) [xcresult-20251018-143052]

$ python3 ${CLAUDE_SKILL_DIR}/scripts/navigator.py --find-text "Sign In" --tap
Tapped: Button "Sign In" at (320, 450)

$ python3 ${CLAUDE_SKILL_DIR}/scripts/wait_for.py --element "Welcome" --timeout 5
OK: element "Welcome" matched in 1.2s

$ python3 ${CLAUDE_SKILL_DIR}/scripts/debug_failing_test.py \
    --project MyApp.xcodeproj --scheme MyApp \
    --test MyAppTests/LoginTests/testInvalidPassword \
    --bundle-id com.example.MyApp
FAIL: testInvalidPassword — bundle: ./debug-20260424-153012/  (3 errors, 142 log lines, ui tree ok, screenshot ok)
```

No pixel coordinates. No walls of build output. No polling loops in the agent turn.

---

## 🧠 Why it works

Three design choices, and the rest follows:

<table>
<tr>
<td width="33%" valign="top">

### 🎯 Semantic, not pixel
Find elements by meaning — `--find-text "Sign In"` — not by `tap 320 400`. Survives UI changes. ~10 tokens vs 1,600–6,300 for a screenshot.

</td>
<td width="33%" valign="top">

### 📦 Progressive disclosure
A build returns one summary line plus an `xcresult-ID`. Pull errors, warnings, or full logs only when you need them. Build output never floods context.

</td>
<td width="33%" valign="top">

### 🤖 Structured outputs
Every script supports `--json` with stable error codes (`NO_BOOTED_SIM`, `ELEMENT_NOT_FOUND`, `BUILD_FAILED`, `TIMEOUT`, …). Agents branch on `code`, not parsed English.

</td>
</tr>
</table>

---

## 📊 The numbers

<div align="center">

| Task | Raw tools | This skill | Savings |
|------|----------:|-----------:|:-------:|
| Screen analysis | 200+ lines | 5 lines | **97.5%** |
| Find & tap button | 100+ lines | 1 line | **99%** |
| Login flow | 400+ lines | 15 lines | **96%** |

### Tested with [Claude Code evals](https://docs.claude.com/en/docs/claude-code/evals)

| Condition | Pass rate |
|:---------:|:---------:|
| **With skill** | 🟢 **100%** (3/3) |
| Without skill | 🔴 46% (~1.4/3) |

</div>

```bash
claude evals run evals/evals.json --skill ios-simulator-skill
```

---

## 📦 Install

### Plugin marketplace (recommended)

```
/plugin marketplace add conorluddy/ios-simulator-skill
/plugin install ios-simulator-skill@conorluddy
```

### Git clone

```bash
# Personal — all your projects
git clone https://github.com/conorluddy/ios-simulator-skill.git \
  ~/.claude/skills/ios-simulator-skill

# Project-scoped
git clone https://github.com/conorluddy/ios-simulator-skill.git \
  .claude/skills/ios-simulator-skill
```

Restart Claude Code. The skill auto-loads when you open iOS files (`.xcodeproj`, `.xcworkspace`, `.swift`, `.m`, `.h`, `Package.swift`).

### Prerequisites

| Requirement | Notes |
|-------------|-------|
| 🍎 macOS 12+ | |
| 🛠️ Xcode CLT | `xcode-select --install` |
| 🐍 Python 3.12+ | |
| 🤖 IDB | Required for UI navigation, screenshots, gestures: `brew tap facebook/fb && brew install idb-companion` |
| 🖼️ Pillow | Only for `visual_diff.py`: `pip3 install pillow` |

> **Just want build tooling, no IDB?** See [xclaude-plugin](https://github.com/conorluddy/xclaude-plugin) — same `xcodebuild` wrapper without the simulator scripts.

---

## ⚡ Quick start

Once installed, ask Claude things like *"build the app and run the login test"* or *"tap the Sign In button and screenshot the result"* — Claude picks the right scripts automatically.

To drive things directly:

```bash
# 1. Verify the environment
bash ~/.claude/skills/ios-simulator-skill/scripts/sim_health_check.sh

# 2. See what's on the screen
python3 ~/.claude/skills/ios-simulator-skill/scripts/screen_mapper.py

# 3. Drive a flow
python3 ~/.claude/skills/ios-simulator-skill/scripts/navigator.py \
  --find-type TextField --enter-text "user@example.com"

python3 ~/.claude/skills/ios-simulator-skill/scripts/navigator.py \
  --find-text "Sign In" --tap

python3 ~/.claude/skills/ios-simulator-skill/scripts/wait_for.py \
  --element "Welcome" --timeout 5
```

> 💡 Set `export SIMCTL_UDID=<your-device-udid>` once and skip `--udid` everywhere.

For the full skill body Claude loads (decision tree + workflows), see [`SKILL.md`](ios-simulator-skill/SKILL.md). For the per-script flag reference, see [`reference.md`](ios-simulator-skill/reference.md). Every script also supports `--help`.

---

## 🧰 Scripts at a glance

> 24 scripts. Every one supports `--help` and `--json`.

<details open>
<summary><b>🏗️ &nbsp; Build & development</b></summary>

| Script | What it does | Key flags |
|--------|-------------|-----------|
| `build_and_test.py` | Build Xcode projects, run tests, parse xcresult with progressive disclosure | `--project` `--scheme` `--test` `--get-errors` `--get-warnings` |
| `log_monitor.py` | Real-time log monitoring with severity filtering | `--app` `--severity` `--follow` `--duration` |

</details>

<details open>
<summary><b>👆 &nbsp; UI navigation</b></summary>

| Script | What it does | Key flags |
|--------|-------------|-----------|
| `screen_mapper.py` | Analyze current screen, list interactive elements | `--verbose` `--hints` |
| `navigator.py` | Find and interact with elements semantically | `--find-text` `--find-type` `--find-id` `--tap` `--enter-text` |
| `gesture.py` | Swipes, scrolls, pinches, long press, pull to refresh | `--swipe` `--scroll` `--pinch` `--long-press` `--refresh` |
| `keyboard.py` | Text input and hardware buttons | `--type` `--key` `--button` `--clear` `--dismiss` |
| `app_launcher.py` | Launch, terminate, install, deep link apps | `--launch` `--terminate` `--install` `--open-url` `--list` |

</details>

<details open>
<summary><b>🧪 &nbsp; Testing & debug</b></summary>

| Script | What it does | Key flags |
|--------|-------------|-----------|
| `wait_for.py` ✨ | Block until an element appears, app reaches a state, or a log line matches | `--element` `--app-state` `--log-match` `--timeout` |
| `debug_failing_test.py` ✨ | Run an XCTest; on failure capture xcresult errors + UI tree + logs + screenshot into one bundle | `--test` `--bundle-id` `--retries` |
| `accessibility_audit.py` | WCAG compliance check on current screen | `--verbose` `--output` |
| `visual_diff.py` | Compare two screenshots | `--threshold` `--output` `--details` |
| `test_recorder.py` | Automated test documentation with screenshots | `--test-name` `--output` |
| `app_state_capture.py` | Debugging snapshot bundle (screenshot + hierarchy + logs) | `--app-bundle-id` `--output` `--log-lines` |
| `model_inspector.py` | Inspect Core Data / SwiftData models from project sources | `--project-path` `--raw` `--show-versions` |
| `sim_health_check.sh` | Verify Xcode, simctl, IDB, Python | — |

</details>

<details>
<summary><b>🔐 &nbsp; Environment & permissions</b></summary>

| Script | What it does | Key flags |
|--------|-------------|-----------|
| `clipboard.py` | Set/assert simulator clipboard for paste testing | `--copy` `--test-name` `--expected` |
| `status_bar.py` | Override status bar for screenshots and demos | `--preset` `--time` `--battery-level` `--clear` |
| `push_notification.py` | Send simulated push notifications | `--bundle-id` `--title` `--body` `--payload` |
| `privacy_manager.py` | Grant, revoke, reset app permissions (13 services) | `--bundle-id` `--grant` `--revoke` `--reset` |

</details>

<details>
<summary><b>🔄 &nbsp; Device lifecycle</b></summary>

| Script | What it does | Key flags |
|--------|-------------|-----------|
| `simctl_boot.py` | Boot simulators with readiness verification | `--name` `--wait-ready` `--timeout` `--all` `--type` |
| `simctl_shutdown.py` | Gracefully shut down simulators | `--name` `--verify` `--all` `--type` |
| `simctl_create.py` | Create simulators by device type and OS version | `--device` `--runtime` `--list-devices` |
| `simctl_delete.py` | Delete simulators with safety confirmation | `--name` `--yes` `--all` `--old` |
| `simctl_erase.py` | Factory reset without deletion | `--name` `--verify` `--all` `--booted` |

</details>

---

## 🎯 Designed for agents

This isn't a CLI library that happens to work with Claude. Every design choice optimizes the agent loop:

- 📉 **Default output is the minimum actionable signal.** 3–5 lines, ~10 tokens. Verbose and JSON modes exist for when you need them.
- 🧬 **Structured error envelopes** with stable codes and optional `recovery_cmd` fields — the script tells the agent how to fix itself.
- 🔁 **`wait_for.py` runs polling on the host.** No more "let me check again" loops eating turns.
- 📁 **`debug_failing_test.py` collapses 5 tools into one bundle** when a test fails — xcresult errors + UI tree + logs + screenshot, indexed by a README.
- 🎛️ **`SIMCTL_UDID` env fallback** — set once, work across all 24 scripts.
- 🚪 **Auto-trigger scoped to iOS files** — won't activate on your Rails project.

---

## 📚 Background reading

- 🔬 [Why accessibility-first navigation matters for AI agents](https://www.conor.fyi/writing/ai-access)
- 📖 [Claude Code skills documentation](https://code.claude.com/docs/en/skills)
- 🧱 [`CLAUDE.md`](CLAUDE.md) — architecture and contribution conventions

---

## 🤝 Contributing

The skill follows the conventions in [`CLAUDE.md`](CLAUDE.md): class-based scripts, `--json` everywhere, terse default output, ruff/black clean. Run `pre-commit run --all-files` before sending a PR. Contract tests for the error envelope live in [`ios-simulator-skill/scripts/tests/`](ios-simulator-skill/scripts/tests/).

PRs welcome — please check existing issues first and keep changes scoped.

---

<div align="center">

### Made for the people who actually have to debug iOS apps at 11pm.

**MIT** · [Issues](https://github.com/conorluddy/ios-simulator-skill/issues) · [Discussions](https://github.com/conorluddy/ios-simulator-skill/discussions)

If this saved you an evening, [⭐ a star](https://github.com/conorluddy/ios-simulator-skill) goes a long way.

</div>
