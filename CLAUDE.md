# CLAUDE.md - Developer Guide

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **completed Agent Skill** for iOS simulator testing, fully distributed as a standalone package that users can install in Claude.ai, Claude Code, or via the Claude API. It provides comprehensive testing and automation capabilities through 10 production-ready scripts wrapping Apple's `xcrun simctl` and Facebook's `idb` tools.

**Key Design Philosophy:**
- Skills are **not MCP servers** - they don't create tool interfaces
- Scripts are **black box helpers** that Claude invokes with structured output
- Focus on **complete testing workflows**, not partial tool exposure
- Progressive disclosure: SKILL.md has minimal context, scripts and references loaded on-demand

## Project Status

### ✅ Implementation Complete

All 12 core scripts are **fully implemented and production-ready**:

1. ✅ `build_and_test.py` (462 lines) - Build automation and test execution
2. ✅ `log_monitor.py` (494 lines) - Real-time log monitoring
3. ✅ `sim_health_check.sh` (239 lines) - Environment verification
4. ✅ `screen_mapper.py` (317 lines) - UI element analysis
5. ✅ `navigator.py` (413 lines) - Element finding and interaction
6. ✅ `gesture.py` (380 lines) - Swipes, scrolls, gestures
7. ✅ `keyboard.py` (410 lines) - Text input and hardware buttons
8. ✅ `app_launcher.py` (394 lines) - App lifecycle control
9. ✅ `accessibility_audit.py` (306 lines) - WCAG compliance checking
10. ✅ `visual_diff.py` (252 lines) - Screenshot comparison
11. ✅ `test_recorder.py` (258 lines) - Test documentation
12. ✅ `app_state_capture.py` (334 lines) - Complete state snapshots

**Total:** ~4,259 lines of production code

### ⏳ Ready for Release

- ✅ All scripts tested and working
- ✅ Complete documentation
- ✅ Reference guides prepared
- ⏳ Git repository initialization
- ⏳ First GitHub release
- ⏳ Marketplace publication

## Skill Format Requirements

### Directory Structure

```
ios-simulator-skill/
├── SKILL.md                 # REQUIRED: Entry point with YAML frontmatter
├── CLAUDE.md                # Developer guide (this file)
├── README.md                # User-facing overview
├── LICENSE                  # MIT
├── scripts/                 # 12 executable production scripts
│   ├── build_and_test.py
│   ├── log_monitor.py
│   ├── sim_health_check.sh
│   ├── screen_mapper.py
│   ├── navigator.py
│   ├── gesture.py
│   ├── keyboard.py
│   ├── app_launcher.py
│   ├── accessibility_audit.py
│   ├── visual_diff.py
│   ├── test_recorder.py
│   └── app_state_capture.py
├── references/             # Deep documentation
│   ├── accessibility_checklist.md
│   ├── troubleshooting.md
│   ├── test_patterns.md
│   ├── idb_quick.md
│   └── simctl_quick.md
└── examples/               # Complete usage examples
    └── login_flow.py
```

### SKILL.md Requirements

**YAML Frontmatter (required):**

```yaml
---
name: ios-simulator-skill          # Must match directory name, hyphen-case only
description: Navigate and interact with iOS apps via accessibility-driven automation
---
```

**Markdown Body:**
- Written in imperative/infinitive form
- Focuses on procedural knowledge and workflows
- Uses progressive disclosure (don't dump everything at once)
- References scripts as black boxes with clear invocation patterns
- Decision tree helps users choose right script for their task

## Architecture & Script Categories

### Category 1: Build & Development (2 scripts)

**Purpose:** Complete the iOS development lifecycle with build automation and debugging support.

#### build_and_test.py (462 lines)
**What it does:** Build Xcode projects and run test suites with token-efficient error parsing.

**Algorithm:**
1. Auto-detect scheme from project/workspace if not specified
2. Build xcodebuild command with appropriate flags
3. Execute build or test operation
4. Parse output for errors and warnings using regex patterns
5. Extract test results from test summary
6. Format token-efficient summary (3-5 lines by default)

**Output formats:**
- Default: 3-5 line summary (status, error/warning counts, top issues)
- `--verbose`: Full build output
- `--json`: Complete structured results

**Key features:**
- Scheme auto-detection
- Build/test in single script
- Intelligent error parsing (groups similar errors)
- Test result parsing from xcresult
- Clean build support
- Simulator selection
- Token-efficient summaries

**Integration points:**
- Uses `sim_health_check.sh` for environment validation
- Produces .app bundles for `app_launcher.py`
- Works with `test_recorder.py` for test documentation

---

#### log_monitor.py (494 lines)
**What it does:** Monitor and analyze iOS simulator logs in real-time with intelligent filtering.

**Algorithm:**
1. Build `xcrun simctl spawn booted log stream` command
2. Add predicate filters for app bundle ID
3. Stream logs line-by-line
4. Classify each line by severity (error/warning/info/debug)
5. Deduplicate repeated messages (signature-based)
6. Store by severity with counts
7. Generate token-efficient summary or stream in follow mode

**Output formats:**
- Default: Summary with error/warning counts and top issues
- `--follow`: Real-time streaming to stdout
- `--json`: Structured log events
- `--output`: Save full logs to file

**Key features:**
- Real-time streaming or duration-based capture
- Severity classification (error/warning/info/debug)
- Deduplication of repeated messages
- Time-based filtering (last N minutes)
- App bundle ID filtering
- Graceful interruption handling (Ctrl+C)
- Token-efficient summaries

**Integration points:**
- Enhanced version of `app_state_capture.py` log capture
- Runs alongside `test_recorder.py` for comprehensive documentation
- Complements `navigator.py` for debugging UI interactions

---

### Category 2: Navigation & Interaction (5 scripts)

**Purpose:** Enable semantic, accessibility-based navigation instead of pixel coordinates.

#### screen_mapper.py (317 lines)
**What it does:** Analyzes current screen to answer "What's visible and interactive?"

**Algorithm:**
1. Call `idb ui describe-all --json --nested`
2. Parse IDB's array format into flat tree structure
3. Count elements by type (Button, TextField, etc.)
4. Extract labels and values
5. Format summary for token efficiency

**Output formats:**
- Default: 5-line token-efficient summary
- `--verbose`: Full element breakdown
- `--hints`: Navigation suggestions
- `--json`: Complete analysis object

**Key features:**
- Element type categorization
- Interactive element counting
- Navigation structure detection
- Text field filling status
- Focusable element identification

---

#### navigator.py (413 lines)
**What it does:** Find and interact with specific UI elements semantically.

**Core capabilities:**
- Find by text (fuzzy or exact)
- Find by element type
- Find by accessibility identifier
- Tap elements at calculated center point
- Enter text into elements
- Tree caching for performance

**Algorithm:**
1. Get accessibility tree (cached)
2. Flatten nested structure
3. Filter by criteria (text, type, ID)
4. Apply fuzzy matching if needed
5. Return nth matching element
6. Tap or enter text
7. Report coordinates and action

**Output:** Single-line summary with action status and coordinates

**Key features:**
- Fuzzy matching for robustness
- Multiple matching strategies
- Caching for repeated operations
- Fallback to coordinate tapping
- Clear failure messages

---

#### gesture.py (380 lines)
**What it does:** Perform swipes, scrolls, and complex touch gestures.

**Supported gestures:**
- Directional swipes (up, down, left, right)
- Multi-swipe scrolling with configurable repetition
- Pull-to-refresh
- Pinch zoom (in and out)
- Long press (tap and hold with duration)
- Drag and drop between points
- Custom swipe between any coordinates

**Screen detection:**
- Auto-detects screen size from device
- Falls back to iPhone 14 defaults (390x844)
- Uses percentage-based positioning for device independence

**Output:** Single-line confirmation of gesture performed

**Key features:**
- Device-aware positioning
- Configurable gesture distance
- Multi-touch simulation
- Delay between multiple gestures
- Smooth vs rapid gesture options

---

#### keyboard.py (410 lines)
**What it does:** Handle text input, special keys, and hardware buttons.

**Capabilities:**
1. Text typing
   - Full text entry at once (efficient)
   - Character-by-character with delays (for animations)

2. Special keys (iOS HID codes)
   - return/enter (40)
   - delete/backspace (42)
   - tab (43), space (44)
   - arrow keys (79-82)
   - escape (41)

3. Hardware buttons
   - home, lock/power
   - volume-up, volume-down
   - ringer, screenshot

4. Key sequences
   - Multiple keys in order
   - Key combinations (Cmd+A, Cmd+C, etc.)

5. Text field operations
   - Clear field (select all + delete)
   - Dismiss keyboard

**Output:** Single-line confirmation of action performed

**Key features:**
- iOS HID code mapping
- Character delay simulation
- Hardware button support
- Key combination support
- Keyboard dismissal strategies

---

#### app_launcher.py (394 lines)
**What it does:** Control app lifecycle and state.

**Capabilities:**
1. Launch apps
   - By bundle ID
   - With debugger attachment
   - Return process ID

2. Terminate apps
   - By bundle ID
   - Graceful shutdown

3. Install/Uninstall
   - From .app bundle paths
   - Verify installation status

4. Deep linking
   - Open custom URLs
   - Deep link navigation

5. App state
   - Check running status
   - Get state (running/suspended/not running)

6. App enumeration
   - List installed apps
   - Filter by type
   - Show app details

**Output:** Single-line confirmation with optional PID or app count

**Key features:**
- Plist parsing for app info
- Process ID extraction
- App state detection
- Deep link support
- App filtering and enumeration

---

### Category 3: Testing & Analysis (5 scripts)

**Purpose:** Provide specialized tools for test automation, debugging, and compliance checking.

#### accessibility_audit.py (306 lines)
**What it does:** Check screen for WCAG accessibility compliance.

**Rules checked:**
1. **Critical (blocking):**
   - Missing accessibility labels on interactive elements
   - Empty button labels
   - Images without alternative text

2. **Warnings (degraded UX):**
   - Missing hints on complex controls
   - Missing accessibility traits
   - Small touch targets (< 44x44pt)

3. **Info (recommendations):**
   - Missing accessibility identifiers
   - Deeply nested views (> 5 levels)

**Algorithm:**
1. Fetch accessibility tree
2. Flatten structure with depth tracking
3. Apply each rule to each element
4. Classify by severity
5. Group issues by type
6. Format for token efficiency

**Output modes:**
- Default: Summary with top 3 issues
- `--verbose`: Complete detailed report
- `--output file.json`: Save full report

**Key features:**
- Severity classification (critical/warning/info)
- Issue grouping and counting
- Actionable fix suggestions
- Exit code based on critical issues
- Token-optimized default output

---

#### visual_diff.py (252 lines)
**What it does:** Compare two screenshots for visual changes.

**Features:**
1. Pixel-by-pixel comparison
2. Difference percentage calculation
3. Threshold-based passing
4. Diff image generation (red highlighting)
5. Side-by-side comparison image
6. JSON report output

**Algorithm:**
1. Load both images
2. Verify dimensions match
3. Convert to RGB
4. Calculate per-pixel differences
5. Count different pixels
6. Calculate percentage
7. Compare to threshold
8. Generate artifacts

**Output:** Pass/fail verdict with change percentage and pixel count

**Output artifacts:**
- `diff.png` - Differences highlighted in red
- `side-by-side.png` - Baseline and current side-by-side
- `diff-report.json` - Detailed metrics

**Key features:**
- Configurable threshold (default 1%)
- Noise filtering (ignore minor variations)
- Multiple image formats supported
- Graceful dimension mismatch handling
- Requires Pillow (optional dependency)

---

#### test_recorder.py (258 lines)
**What it does:** Automatically document test execution with screenshots and state.

**Features:**
1. Step-based recording
2. Automatic screenshot per step
3. Accessibility tree snapshots
4. Timestamped artifacts
5. Markdown report generation
6. Metadata JSON output
7. Optional assertion tracking

**Algorithm:**
1. Create timestamped output directory
2. For each step:
   - Increment step counter
   - Capture screenshot
   - Capture accessibility tree
   - Count UI elements
   - Store step metadata
   - Print token-efficient status

3. Generate outputs:
   - Markdown report with screenshots
   - JSON metadata with step timing
   - Directory structure with artifacts

**Output:** Step-by-step confirmations during recording; report path when complete

**Output structure:**
```
test-name-TIMESTAMP/
├── report.md (markdown with screenshots and assertions)
├── metadata.json (complete timing and step data)
├── screenshots/ (numbered screenshots)
└── accessibility/ (UI trees per step)
```

**Key features:**
- Automatic timestamping
- Element counting
- Assertion support
- Markdown report generation
- Accessible artifact organization

---

#### app_state_capture.py (334 lines)
**What it does:** Create comprehensive debugging snapshots.

**Captures:**
1. Screenshot
2. Accessibility tree (full UI hierarchy)
3. App logs (last N lines, filtered by app)
4. Device information
5. Error/warning detection
6. Summary markdown

**Algorithm:**
1. Create timestamped capture directory
2. Capture screenshot
3. Fetch accessibility tree and count elements
4. If app ID provided:
   - Stream recent logs
   - Parse for errors/warnings
   - Limit to N lines
5. Get device info (name, UDID, state)
6. Generate summary markdown
7. Save JSON metadata

**Output:** Directory path with summary of captured items

**Output structure:**
```
app-state-TIMESTAMP/
├── screenshot.png
├── accessibility-tree.json
├── app-logs.txt
├── device-info.json
├── summary.json
└── summary.md
```

**Key features:**
- Complete state capture
- Log filtering by app
- Error/warning counting
- Device information extraction
- Human-readable markdown summary

---

#### sim_health_check.sh (239 lines)
**What it does:** Verify environment is configured for iOS simulator testing.

**Checks performed (8 checks):**
1. macOS detection
2. Xcode Command Line Tools
3. simctl availability
4. IDB installation (optional)
5. Python 3 installation
6. Available simulators
7. Booted simulators
8. Python packages (Pillow for visual_diff)

**Output:** Colored status for each check with actionable error messages

**Exit codes:**
- 0: All checks passed
- 1: One or more failures

**Key features:**
- Colored output (Green/Red/Yellow)
- Xcode version detection
- Simulator enumeration
- Package availability checking
- Actionable error messages
- Optional dependency warnings

---

## Script Implementation Patterns

### Bash Scripts

```bash
#!/usr/bin/env bash
set -e  # Exit on error

# Always provide --help
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    cat <<EOF
Script Name - Description

Usage: bash scripts/script_name.sh [options]
...
EOF
    exit 0
fi

# Main implementation
```

### Python Scripts

```python
#!/usr/bin/env python3
"""
Script description with docstring.

Key features and usage examples.
"""
import argparse
import subprocess
import sys
from typing import Optional

class ScriptClass:
    """Main class for script functionality."""

    def __init__(self, udid: Optional[str] = None):
        """Initialize with optional device UDID."""
        self.udid = udid

    def core_method(self):
        """Main functionality."""
        pass

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='...')
    parser.add_argument('--udid', help='Device UDID')
    # ... more args

    args = parser.parse_args()
    # Implementation

if __name__ == '__main__':
    main()
```

### Key Principles

**Security:**
- Use `subprocess.run()` with list arguments, NEVER `shell=True` for user input
- Validate file paths before operations
- Sanitize user input for command execution

**Error Handling:**
- Catch specific exceptions, provide actionable error messages
- Never silently fail or swallow errors
- Include suggestions for fixing issues

**Output:**
- JSON for machine-readable data
- Formatted text for human-readable (default)
- Progressive detail with `--verbose` and `--json` flags

**Defaults:**
- Use "booted" simulator if no UDID specified
- Provide sensible command-line defaults
- Token-efficient output by default

## Tool Invocation Patterns

### IDB Commands

```bash
# Get booted device
idb list-targets

# UI automation
idb ui tap 200 400 --udid <device-id>
idb ui swipe 100 500 100 200 --udid <device-id>
idb ui describe-all --udid <device-id> --json --nested
idb ui text "text to type" --udid <device-id>
idb ui key <key-code> --udid <device-id>

# Screenshots
idb screenshot --udid <device-id> output.png
```

### simctl Commands

```bash
# List devices
xcrun simctl list devices
xcrun simctl list devices available
xcrun simctl list devices booted

# Boot/launch
xcrun simctl boot <device-udid>
xcrun simctl launch booted <bundle-id>
xcrun simctl terminate booted <bundle-id>

# Screenshots/video
xcrun simctl io booted screenshot output.png
xcrun simctl io booted recordVideo output.mp4

# Logs
xcrun simctl spawn booted log stream --predicate 'process == "<app-name>"'

# Apps
xcrun simctl install booted <app-path>
xcrun simctl uninstall booted <bundle-id>
xcrun simctl listapps booted
```

## Design Decisions & Rationale

### 1. 10 Scripts, Not 50+

**Decision:** Expose 15-20 high-value commands through dedicated scripts, not every possible tool.

**Rationale:**
- **Jackson's Law**: Minimal code to solve problems
- **Progressive disclosure**: Users can access raw tools if needed
- **Focused workflows**: Each script solves a specific problem
- **Maintainability**: Fewer scripts to test and document

---

### 2. Python for Logic, Bash for System Checks

**Decision:**
- Bash for environment checks and simple wrappers
- Python for JSON parsing, complex logic, image processing

**Rationale:**
- Bash is universal but poor at structured data
- Python handles JSON and image processing natively
- Python provides better error handling and type safety
- Bash good for quick system checks and colorized output

---

### 3. Accessibility Audit: 5-10 Core Rules, Not 50+

**Decision:** Implement high-impact WCAG rules, avoid false positives.

**Rationale:**
- 80/20 rule: Most critical accessibility issues caught by core rules
- False positives cause alert fatigue
- Can expand rule set based on user feedback
- Token-efficient: Rules are fast to compute

---

### 4. Output Formats: Human-Readable Default, Machine-Readable on Request

**Decision:**
- Default: Minimal, formatted text (3-5 lines)
- `--verbose`: Full details
- `--json`: Complete structured data

**Rationale:**
- Primary user is developer running ad-hoc tests
- AI agents prefer JSON but humans need readable output
- Progressive disclosure keeps token count low
- `--help` documents all options

---

### 5. Error Handling: Fail Fast with Actionable Messages

**Decision:** Exit on error immediately, always explain why and how to fix.

**Rationale:**
- Quick feedback loop enables debugging
- Actionable messages reduce user frustration
- Clear errors are better than silent failures
- Enables integration into CI/CD pipelines

**Pattern:**
```
Error: Failed to launch app
Reason: Bundle ID 'com.wrong.app' not found
Solution: Run 'python scripts/app_launcher.py --list' to find correct bundle ID
```

---

### 6. Semantic Finding Over Coordinates

**Decision:** Find by text, type, and ID - NOT pixel coordinates.

**Rationale:**
- Pixel coordinates are fragile (break on UI changes)
- Semantic finding adapts to layout changes
- Accessibility data is available and reliable
- Matches how humans understand UI

---

### 7. Token Efficiency Through Summarization

**Decision:** Provide top-3 summaries by default, not full details.

**Rationale:**
- AI agents need structured summaries, not raw dumps
- Full JSON available on request via `--json`
- Grouping reduces token count significantly
- Examples: top accessibility issues, top elements by type

---

## Common Patterns to Reuse

### Getting Booted Simulator

```python
def get_booted_device_id() -> Optional[str]:
    """Get UDID of currently booted simulator, or None."""
    result = subprocess.run(
        ['xcrun', 'simctl', 'list', 'devices', 'booted'],
        capture_output=True,
        text=True
    )

    for line in result.stdout.split('\n'):
        if 'iPhone' in line or 'iPad' in line:
            match = re.search(r'\(([A-F0-9-]+)\)', line)
            if match:
                return match.group(1)
    return None
```

### Parsing IDB Accessibility Tree

```python
def get_accessibility_tree(udid: Optional[str]) -> Dict:
    """Get accessibility tree from IDB."""
    cmd = ['idb', 'ui', 'describe-all', '--json', '--nested']
    if udid:
        cmd.extend(['--udid', udid])

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    tree_data = json.loads(result.stdout)

    # IDB returns array, extract first element
    if isinstance(tree_data, list) and len(tree_data) > 0:
        return tree_data[0]
    return tree_data
```

### JSON Output with Fallback

```python
def output_results(results: Dict, output_file: Optional[str] = None):
    """Output results as JSON to file or stdout."""
    json_output = json.dumps(results, indent=2)

    if output_file:
        with open(output_file, 'w') as f:
            f.write(json_output)
        print(f"Results saved to: {output_file}")
    else:
        print(json_output)
```

### Argument Parsing

```python
parser = argparse.ArgumentParser(description='Script description')
parser.add_argument('--udid', help='Device UDID (uses booted if not specified)')
parser.add_argument('--output', help='Output file (default: stdout)')
parser.add_argument('--verbose', action='store_true', help='Show detailed output')
parser.add_argument('--json', action='store_true', help='Output as JSON')

args = parser.parse_args()
```

## Script Security

### Command Injection Prevention

```python
# ✅ Safe - list arguments
subprocess.run(['idb', 'ui', 'tap', str(x), str(y)])

# ❌ Unsafe - shell interpolation
subprocess.run(f'idb ui tap {x} {y}', shell=True)
```

**Rule:** NEVER use `shell=True` with user input.

### Path Handling

```python
import pathlib

def validate_path(path: str) -> str:
    """Ensure path is within allowed locations."""
    resolved = pathlib.Path(path).resolve()
    if not str(resolved).startswith(str(pathlib.Path.home())):
        raise ValueError(f"Path outside home directory: {path}")
    return str(resolved)
```

## Development Workflow

### Creating New Scripts

1. **Define purpose**: What specific workflow does this enable?
2. **Check SKILL.md**: Is this workflow already documented? Add/update it.
3. **Implement script**:
   - Start with `--help` documentation
   - Use type hints (Python)
   - Handle errors with actionable messages
   - Test with real simulator
4. **Update SKILL.md**: Add usage examples for the new script
5. **Document in references/**: If complex, add detailed guide

### Testing Scripts

```bash
# 1. Run health check
bash scripts/sim_health_check.sh

# 2. Boot simulator
open -a Simulator

# 3. Test script with real simulator
python scripts/script_name.py --help
python scripts/script_name.py

# 4. Verify output format
python scripts/script_name.py --json | jq .  # Validate JSON
```

### Adding Reference Documentation

Reference docs (`references/`) provide **deep knowledge** loaded on-demand:

- `accessibility_checklist.md` - Complete WCAG guidelines for iOS
- `troubleshooting.md` - Known simulator bugs, workarounds
- `test_patterns.md` - Additional workflow templates
- `idb_quick.md` - IDB command reference
- `simctl_quick.md` - simctl command reference

**Format:** Markdown with code examples, patterns, and troubleshooting.

## Distribution

### As Claude Code Skill

Users install via marketplace or direct download:

```bash
# Personal installation
git clone <repo-url> ~/.claude/skills/ios-simulator-skill

# Team installation
git clone <repo-url> .claude/skills/ios-simulator-skill
```

Then restart Claude Code to load.

### Requirements File

If scripts need Python packages, document in SKILL.md (don't use requirements.txt):

```bash
# Optional dependencies
pip3 install pillow  # For visual_diff.py
```

Skills don't use pip install pattern - users install packages manually if needed.

## Key Differences from MCP Servers

| Aspect | MCP Server | This Skill |
|--------|-----------|-----------|
| Creates tools | Yes - tool interfaces | No - helper scripts |
| Runs as process | Yes - stdio server | No - passive directory |
| Distribution | NPM package | Git repo / upload |
| Integration | Requires MCP client | Native to Claude |
| Language | TypeScript typical | Any (bash/python here) |
| Skill loading | Not applicable | Auto-detected by Claude |
| Input/output | Structured JSON only | Flexible (text/JSON/files) |

## Important Constraints

1. **No MCP Tool Creation** - Skills can't create tool interfaces (that's MCP servers)
2. **Scripts are Helpers** - Claude invokes scripts, parses output; not programmatic tools
3. **Black Box Usage** - SKILL.md tells Claude to run scripts with `--help`, not read source
4. **Progressive Disclosure** - Load references/ and examples/ only when needed
5. **Self-Contained** - Can't assume external dependencies beyond system tools

## Next Steps for Enhancement

**Potential future additions:**
- Network recording/playback for offline testing
- Gesture recording (record user interactions, replay)
- Performance profiling
- Memory leak detection
- Network mocking
- Custom assertion framework
- CI/CD integration examples
- Android simulator support (parallel track)

**Keep in mind:**
- Each addition must maintain token efficiency
- Avoid feature creep (Jackson's Law)
- Test with real users before adding
- Document thoroughly

## Code Quality Standards

All code in this repository follows:

- **Jackson's Law**: Minimal code to solve the problem
- **Guard clauses**: Validate inputs first, happy path last
- **Functions < 50 lines**: Keep functions focused
- **Files < 300 lines**: Keep modules understandable
- **Actionable errors**: Never "Error: failed", always explain what and how to fix
- **Type hints**: Python code uses type annotations
- **Comments explain why**: Not what code does, but why it exists
- **DRY principle**: Don't repeat logic across scripts
- **Security first**: Never shell=True, always validate paths

## License

MIT - Allowing commercial use and distribution.

---

**Last updated:** October 2025

**Status:** Production Ready - All scripts implemented, documented, and tested.
