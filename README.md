# iOS Simulator Skill

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Efficient iOS app building, navigation, and testing using accessibility-first automation. Optimized for AI agents with minimal token output and maximum capability.

## Features

🎯 **12 Production Scripts** - Complete toolkit for iOS development and testing
🔧 **Build Automation** - Build projects and run tests with intelligent error parsing
📊 **Token-Efficient** - 97% reduction in output tokens vs raw tools
♿ **Accessibility-First** - Use structured data and semantic navigation, not pixels
🚀 **Zero Config** - Works immediately on any macOS with Xcode
🤖 **AI-Optimized** - Progressive disclosure with `--verbose` and `--json` flags
🔍 **Debugging Tools** - Real-time log monitoring, state capture, visual diffs

## What You Get

### Build & Development Tools (2 scripts)
- **build_and_test.py** - Build Xcode projects and run test suites with smart error parsing
- **log_monitor.py** - Real-time log streaming with intelligent filtering and error detection

### Navigation Tools (5 scripts)
- **screen_mapper.py** - Analyze current screen in 5 lines
- **navigator.py** - Find and interact with elements semantically
- **gesture.py** - Swipes, scrolls, pinches, and complex gestures
- **keyboard.py** - Text input and hardware button control
- **app_launcher.py** - App lifecycle (launch, terminate, install, deep links)

### Testing & Analysis Tools (5 scripts)
- **accessibility_audit.py** - WCAG compliance checking with severity levels
- **visual_diff.py** - Pixel-by-pixel screenshot comparison for regression testing
- **test_recorder.py** - Automated test documentation with screenshots
- **app_state_capture.py** - Complete debugging snapshots (screen, tree, logs)
- **sim_health_check.sh** - Environment verification

## Quick Start

### Prerequisites

```bash
# macOS with Xcode Command Line Tools
xcode-select --install

# IDB (recommended, not required)
brew tap facebook/fb
brew install idb-companion

# Python 3 (usually pre-installed on macOS)
python3 --version
```

### Installation as Claude Code Skill

**Option 1: Personal Skill (recommended for individual use)**

```bash
# Clone into your personal skills directory
git clone <repo-url> ~/.claude/skills/ios-simulator-skill

# Restart Claude Code to load the skill
```

**Option 2: Project Skill (recommended for teams)**

```bash
# Clone into your project's skills directory
cd /path/to/your/project
git clone <repo-url> .claude/skills/ios-simulator-skill

# Commit to share with your team
git add .claude/skills/ios-simulator-skill
git commit -m "Add iOS simulator navigation skill"
```

**Verify Installation:**

```bash
# Check the skill is available
ls ~/.claude/skills/ios-simulator-skill/SKILL.md

# Run health check
bash ~/.claude/skills/ios-simulator-skill/scripts/sim_health_check.sh
```

### Using the Skill in Claude Code

Once installed, Claude Code **automatically detects when to use this skill** based on your requests. You don't need to manually invoke it!

**Example conversations:**

```
You: "Navigate to the login screen in my iOS simulator"
Claude: [Automatically uses ios-simulator-skill to map screen and find login elements]

You: "Fill in the username field with test@example.com"
Claude: [Uses navigator.py to find and enter text]

You: "What buttons are available on this screen?"
Claude: [Uses screen_mapper.py to analyze and list interactive elements]

You: "Check this screen for accessibility issues"
Claude: [Uses accessibility_audit.py to run compliance checks]
```

**Manual Script Usage (optional):**

You can also run scripts directly:

```bash
# 1. Health check (verify everything works)
bash ~/.claude/skills/ios-simulator-skill/scripts/sim_health_check.sh

# 2. Launch your app
python ~/.claude/skills/ios-simulator-skill/scripts/app_launcher.py --launch com.example.app

# 3. See what's on screen (5 lines output!)
python ~/.claude/skills/ios-simulator-skill/scripts/screen_mapper.py

# 4. Tap a button
python ~/.claude/skills/ios-simulator-skill/scripts/navigator.py --find-text "Login" --tap

# 5. Enter text
python ~/.claude/skills/ios-simulator-skill/scripts/navigator.py --find-type TextField --enter-text "hello@example.com"

# 6. Check accessibility compliance
python ~/.claude/skills/ios-simulator-skill/scripts/accessibility_audit.py

# 7. Compare screenshots
python ~/.claude/skills/ios-simulator-skill/scripts/visual_diff.py baseline.png current.png

# 8. Capture complete app state
python ~/.claude/skills/ios-simulator-skill/scripts/app_state_capture.py --app-bundle-id com.example.app

# 9. Record test with documentation
python ~/.claude/skills/ios-simulator-skill/scripts/test_recorder.py --test-name "Login Flow"

# 10. Perform gestures
python ~/.claude/skills/ios-simulator-skill/scripts/gesture.py --swipe up
```

## All 10 Scripts Overview

| Script | Purpose | Output | Key Features |
|--------|---------|--------|--------------|
| `screen_mapper.py` | Analyze current screen | 5 lines | Element types, button lists, counts |
| `navigator.py` | Find & interact with elements | 1 line | Fuzzy text matching, type matching, coordinates |
| `gesture.py` | Perform touches & gestures | 1 line | Swipes, scrolls, pinches, long-press, drag |
| `keyboard.py` | Text entry & hardware control | 1 line | Special keys, hardware buttons, combos |
| `app_launcher.py` | App lifecycle control | 1 line | Launch, terminate, install, deep links, state |
| `accessibility_audit.py` | Check WCAG compliance | 3-5 lines | Critical/warning/info issues, structured JSON |
| `visual_diff.py` | Screenshot comparison | 1-2 lines | Pixel diff, threshold testing, artifacts |
| `test_recorder.py` | Document test execution | 1 line per step | Screenshots, accessibility trees, markdown reports |
| `app_state_capture.py` | Complete state snapshot | 3 lines | Screen, UI tree, logs, device info |
| `sim_health_check.sh` | Verify environment | 10 lines | Check all dependencies, versions, available devices |

## Complete Usage Examples

### Example 1: Login Flow (Fully Automated)

```bash
# Boot simulator
open -a Simulator

# Run health check
bash scripts/sim_health_check.sh

# Launch app
python scripts/app_launcher.py --launch com.example.app

# Map screen to see what's available
python scripts/screen_mapper.py
# Output:
# Screen: LoginViewController (45 elements, 7 interactive)
# Buttons: "Login", "Cancel", "Forgot Password"
# TextFields: 2 (0 filled)
# Navigation: NavBar: "Sign In"
# Focusable: 7 elements

# Enter username
python scripts/navigator.py --find-type TextField --index 0 --enter-text "user@test.com"

# Enter password
python scripts/navigator.py --find-type SecureTextField --enter-text "password123"

# Tap login button
python scripts/navigator.py --find-text "Login" --tap

# Verify successful login with accessibility audit
python scripts/accessibility_audit.py
```

### Example 2: Form Filling with Validation

```bash
# Map screen to find form fields
python scripts/screen_mapper.py --verbose

# Fill multi-field form (Name → Email → Phone)
python scripts/navigator.py --find-id "nameField" --enter-text "John Doe"
python scripts/keyboard.py --key tab
python scripts/keyboard.py --type "john@example.com"
python scripts/keyboard.py --key tab
python scripts/keyboard.py --type "5551234567"

# Submit form
python scripts/navigator.py --find-text "Submit" --tap

# Check for accessibility issues
python scripts/accessibility_audit.py --verbose
```

### Example 3: Navigation with Scrolling

```bash
# Map current screen
python scripts/screen_mapper.py

# Find and tap menu
python scripts/navigator.py --find-text "Menu" --tap

# Scroll down to see more items
python scripts/gesture.py --scroll down --scroll-amount 3

# Tap result
python scripts/navigator.py --find-text "Settings" --tap

# Use tab gesture
python scripts/gesture.py --swipe left
```

### Example 4: Visual Regression Testing

```bash
# Take baseline screenshot
python scripts/app_state_capture.py --output baseline/

# Make changes to app/design

# Take current screenshot
python scripts/app_state_capture.py --output current/

# Compare visually
python scripts/visual_diff.py baseline/screenshot.png current/screenshot.png --threshold 0.02

# Check accessibility hasn't regressed
python scripts/accessibility_audit.py
```

### Example 5: Test Recording & Documentation

```bash
# Start recording
python scripts/test_recorder.py --test-name "User Registration Flow" --output test-reports/

# In another terminal, interact with app:
# Then manually record each step by calling recorder.step()

# This generates:
# - test-reports/user-registration-flow-TIMESTAMP/
#   ├── report.md (markdown with screenshots)
#   ├── metadata.json (complete test data)
#   ├── screenshots/ (numbered screenshots)
#   └── accessibility/ (UI trees per step)
```

### Example 6: Complete Debugging Snapshot

```bash
# Capture everything for bug reproduction
python scripts/app_state_capture.py \
  --app-bundle-id com.example.app \
  --output bug-reports/ \
  --log-lines 200

# Generates:
# - app-state-TIMESTAMP/
#   ├── screenshot.png (current screen)
#   ├── accessibility-tree.json (full UI hierarchy)
#   ├── app-logs.txt (app error logs)
#   ├── device-info.json (device details)
#   ├── summary.json (metadata)
#   └── summary.md (human-readable report)
```

## How It Works with Claude Code

### Automatic Discovery

Claude Code reads the `SKILL.md` file's description to understand when to use this skill:

```yaml
---
name: ios-simulator-skill
description: Navigate and interact with iOS apps via accessibility-driven automation
---
```

When you ask Claude to:
- Navigate an iOS app
- Interact with simulator UI elements
- Test iOS app functionality
- Inspect accessibility of iOS screens
- Compare visual changes
- Debug app state

Claude **automatically loads this skill** and uses the appropriate scripts.

### Progressive Disclosure

Claude doesn't load everything at once. It follows this pattern:

1. **Initial context**: Reads SKILL.md (lightweight workflow guide)
2. **When needed**: Loads specific scripts with `--help`
3. **For details**: Accesses references/ documentation
4. **For examples**: Checks examples/ directory

This keeps token usage minimal while providing full capabilities.

## Why This Skill?

**Problem:** Raw iOS automation tools generate 100s of lines of output, wasting tokens and making it hard for AI agents to work effectively.

**Solution:** Token-efficient wrappers that output 3-5 lines by default while maintaining full functionality.

### Token Comparison

| Task | Raw Tools | This Skill | Savings |
|------|-----------|-----------|---------|
| Screen analysis | 200+ lines | 5 lines | 97.5% |
| Find & tap button | 100+ lines | 1 line | 99% |
| Enter text | 50+ lines | 1 line | 98% |
| Complete login flow | 400+ lines | 15 lines | 96% |
| Accessibility audit | N/A | 3-5 lines | Baseline |
| Visual diff check | N/A | 1-2 lines | Baseline |

## Accessibility-First Approach

Instead of pixel-based navigation (which breaks when UI changes):

```bash
# ❌ Fragile - breaks if UI changes
idb ui tap 320 400  # What's at 320,400?
```

Use semantic navigation (which adapts):

```bash
# ✅ Robust - finds by meaning
python scripts/navigator.py --find-text "Login" --tap
```

**Benefits:**
- More reliable (semantic vs pixels)
- More maintainable (no hardcoded coordinates)
- More token-efficient (structured data vs screenshots)
- Faster (no image processing)

## Requirements

- **macOS 12+** (iOS Simulator requires macOS)
- **Xcode Command Line Tools** (`xcode-select --install`)
- **Python 3.x** (pre-installed on macOS)
- **IDB** (optional but recommended, `brew install idb-companion`)
- **Pillow** (optional, for visual_diff.py: `pip3 install pillow`)

## Use Cases

- 🤖 **AI Agent Automation** - Token-efficient app navigation for Claude
- 🧪 **Manual Testing** - Quick verification workflows
- 📱 **App Exploration** - Understand app structure and interactions
- 🔍 **Debugging** - Inspect UI hierarchy and capture state
- 📸 **State Capture** - Generate bug reports with screenshots
- ♿ **Accessibility Testing** - Check WCAG compliance
- 📊 **Visual Testing** - Detect UI regressions
- 📝 **Test Documentation** - Auto-generate test reports

## Project Structure

```
ios-simulator-skill/
├── SKILL.md                      # Main entry point (loads in Claude Code)
├── CLAUDE.md                     # Developer guide for AI agents
├── README.md                     # This file
├── LICENSE                       # Apache 2.0
├── scripts/                      # 10 production scripts
│   ├── screen_mapper.py         # Screen analysis
│   ├── navigator.py             # Element finding & interaction
│   ├── gesture.py               # Swipes & gestures
│   ├── keyboard.py              # Text input & hardware buttons
│   ├── app_launcher.py          # App lifecycle
│   ├── accessibility_audit.py   # WCAG compliance checking
│   ├── visual_diff.py           # Screenshot comparison
│   ├── test_recorder.py         # Test documentation
│   ├── app_state_capture.py     # Debugging snapshots
│   └── sim_health_check.sh      # Environment verification
├── references/                   # Deep dive documentation
│   ├── accessibility_checklist.md
│   ├── troubleshooting.md
│   ├── test_patterns.md
│   ├── idb_quick.md
│   └── simctl_quick.md
└── examples/                     # Complete usage examples
    └── login_flow.py
```

## Documentation

- **SKILL.md** - Complete usage guide with all 10 scripts and workflows
- **CLAUDE.md** - Developer guide for AI agents and contributions
- **README.md** - This file (overview and getting started)
- **references/** - Deep dive into specific topics
- **examples/** - Complete automation examples

## Contributing

This is an Agent Skill designed for the Claude Code ecosystem. Contributions should:

- Maintain token efficiency (minimal output by default)
- Follow accessibility-first patterns
- Include `--help` documentation
- Provide `--verbose` for detailed output
- Handle errors with actionable messages
- Add tests and examples
- Update SKILL.md with new workflows

## License

Apache 2.0 - See [LICENSE](LICENSE) for details. Allows commercial use and distribution.

## Acknowledgments

Built for the Claude Code Agent Skills ecosystem (October 2025).

**Wraps:**
- Apple's `xcrun simctl` - iOS Simulator control
- Facebook's `idb` - iOS Development Bridge

**Inspired by:**
- The need for token-efficient automation in AI agent workflows
- Accessibility-first design principles
- Minimal, focused tooling over feature bloat

## Troubleshooting

### Skill Not Loading

```bash
# 1. Check skill is in correct location
ls ~/.claude/skills/ios-simulator-skill/SKILL.md

# 2. Verify SKILL.md has valid YAML frontmatter
head -5 ~/.claude/skills/ios-simulator-skill/SKILL.md

# 3. Restart Claude Code
# Skills are loaded at startup - changes require restart
```

### Claude Not Using Skill Automatically

- Check that your request matches the skill description keywords
- Try being more specific: "Use the iOS simulator skill to navigate this app"
- Verify skill is installed in `~/.claude/skills/` or `.claude/skills/`

### Scripts Not Running

```bash
# Ensure scripts are executable
chmod +x ~/.claude/skills/ios-simulator-skill/scripts/*.sh

# Check Python 3 is available
python3 --version

# Verify IDB is installed (if using navigation features)
idb --version
```

### Environment Issues

Run the health check to diagnose:

```bash
bash ~/.claude/skills/ios-simulator-skill/scripts/sim_health_check.sh
```

This checks: macOS, Xcode, simctl, IDB, Python, available simulators, and Python packages.

### Specific Script Issues

Each script supports `--help`:

```bash
python scripts/navigator.py --help
python scripts/screen_mapper.py --help
python scripts/accessibility_audit.py --help
# etc.
```

## Support

- **Issues**: Create GitHub issue with reproduction steps
- **Questions**: See SKILL.md and references/ for detailed docs
- **Examples**: Check examples/ directory for complete workflows
- **Claude Code Skills Docs**: https://docs.claude.com/en/docs/claude-code/skills

---

**Built for AI agents. Optimized for humans.**

Combine all 10 scripts to automate iOS testing workflows that would take hours to implement manually.
