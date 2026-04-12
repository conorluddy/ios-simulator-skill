[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/conorluddy/ios-simulator-skill)

# iOS Simulator Skill for Claude Code

Production-ready skill for building, testing, and automating iOS apps. 21 scripts optimized for both human developers and AI agents.

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

When screenshots are needed (visual verification, bug reports, diffs), the skill automatically resizes and compresses them to minimize token cost. Default output across all 21 scripts is 3-5 lines — 96% reduction vs raw tool output.

| Task | Raw Tools | This Skill | Savings |
|------|-----------|-----------|---------|
| Screen analysis | 200+ lines | 5 lines | 97.5% |
| Find & tap button | 100+ lines | 1 line | 99% |
| Login flow | 400+ lines | 15 lines | 96% |

### All 21 Scripts

**Build & Development** — `build_and_test.py`, `log_monitor.py`

**Navigation & Interaction** — `screen_mapper.py`, `navigator.py`, `gesture.py`, `keyboard.py`, `app_launcher.py`

**Testing & Analysis** — `accessibility_audit.py`, `visual_diff.py`, `test_recorder.py`, `app_state_capture.py`, `sim_health_check.sh`

**Permissions & Environment** — `clipboard.py`, `status_bar.py`, `push_notification.py`, `privacy_manager.py`

**Device Lifecycle** — `simctl_boot.py`, `simctl_shutdown.py`, `simctl_create.py`, `simctl_delete.py`, `simctl_erase.py`

Every script supports `--help` and `--json`. See **SKILL.md** for the complete reference.

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
