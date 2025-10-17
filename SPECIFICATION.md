# iOS Simulator Testing Skill - Technical Specification

**Version:** 1.0.0
**Created:** 2025-10-17
**Status:** Planning Phase

## Executive Summary

This document specifies the architecture, design decisions, and implementation plan for the iOS Simulator Testing Agent Skill. The skill provides testing workflows for iOS applications running in simulators through wrapper scripts around Apple's `xcrun simctl` and Facebook's `idb` tools.

**Core Principle:** Progressive disclosure. We expose high-value testing workflows without overwhelming users with every possible tool option. Advanced users can still access underlying tools directly.

## Alignment with Code Style Guidelines

### From CODESTYLE.md

**Jackson's Law Applied:**
- Minimal code to solve testing problems correctly
- Each script is self-contained, single-purpose
- No premature abstraction - wait for 3rd use case before extracting patterns

**Progressive Disclosure:**
- SKILL.md provides high-level workflows (loaded first)
- Scripts provide focused functionality (loaded on-demand via `--help`)
- References provide deep knowledge (loaded only when needed)

**Guard Clauses:**
- All scripts validate environment/inputs first
- Happy path clearly visible at script end
- Fail fast with actionable error messages

### From CODESTYLE_MAX.md

**Context as Finite Resource:**
- Each script is a **context boundary** - complete understanding without cross-references
- Token-efficient outputs: summaries with drill-down capability
- Structured sections with clear boundaries

**Self-Contained Context Units:**
- Explicit dependencies in function signatures
- Clear input/output contracts with type hints
- Comprehensive docstrings with usage examples

**Long-Horizon Task Support:**
- Test recorder maintains state across test steps
- Structured output enables resumption after interruption

## Architecture Overview

### The Three-Layer Model

```
Layer 1: SKILL.md (Workflow Documentation)
         ↓ References workflows
Layer 2: Scripts (Executable Black Boxes)
         ↓ Wraps commands
Layer 3: Underlying Tools (simctl, idb)
```

**Design Decision:** Users interact primarily with Layer 1 and 2. Layer 3 is abstracted but documented in references/ for advanced users.

### Module Organization

```
ios-simulator-skill/
├── SKILL.md                    # Layer 1: High-level workflows
├── CLAUDE.md                   # Developer guide for AI agents
├── SPECIFICATION.md            # This document
├── LICENSE                     # Apache 2.0
├── README.md                   # Distribution/installation guide
│
├── scripts/                    # Layer 2: Executable helpers
│   ├── sim_health_check.sh     # Environment verification
│   ├── accessibility_audit.py  # WCAG compliance checking
│   ├── visual_diff.py          # Screenshot comparison
│   ├── test_recorder.py        # Test execution documentation
│   ├── app_state_capture.py    # App state snapshot
│   └── lib/                    # Shared utilities (if needed)
│       └── common.py           # Shared Python functions
│
├── references/                 # Layer 3: Deep knowledge
│   ├── simctl_reference.md     # Extracted simctl documentation
│   ├── idb_reference.md        # Extracted idb documentation
│   ├── accessibility_checklist.md  # WCAG patterns for iOS
│   ├── common_issues.md        # Known problems and workarounds
│   └── test_patterns.md        # Additional workflow templates
│
└── examples/                   # Complete demonstrations
    ├── login_flow_test.py      # Full test example
    └── screenshots/            # Example outputs
```

## Underlying Tool Capabilities

### xcrun simctl (Apple's Simulator Control)

**Core Capabilities We'll Expose:**
- Device lifecycle: `boot`, `shutdown`, `list devices`
- App management: `install`, `launch`, `terminate`
- Media operations: `io screenshot`, `io recordVideo`
- Status/info: `get_app_container`, `listapps`, `appinfo`

**Capabilities We'll Skip (Low Value for Testing):**
- `create`, `delete`, `clone` - device management better done via Xcode
- `pair`, `unpair` - watch-specific, niche use case
- `privacy` - complex, requires deep understanding
- `keychain` - security-sensitive, better handled manually

**Documented in:** `references/simctl_reference.md`

### idb (Facebook's iOS Development Bridge)

**Core Capabilities We'll Expose:**
- UI automation: `ui tap`, `ui swipe`, `ui text`, `ui describe-all`, `ui describe-point`
- Accessibility: `ui describe-all --json --nested` (foundation of accessibility_audit.py)
- Screenshots: `screenshot` (fallback if simctl unavailable)
- App info: `list-apps`, `describe`

**Capabilities We'll Skip:**
- `xctest` - complex, requires test bundles
- `debugserver`, `instruments` - development tools, not testing
- `companion` management - infrastructure, not user-facing
- `dsym`, `crash` - debugging, separate concern

**Documented in:** `references/idb_reference.md`

## Script Specifications

### Design Principles for All Scripts

1. **Self-Contained**: Each script complete without reading others
2. **Explicit Contract**:
   - `--help` explains all parameters
   - Type hints for Python
   - Clear exit codes (0 = success, 1 = failure)
3. **Actionable Errors**: Never "Error: failed" - always explain what and how to fix
4. **Default to "booted"**: If no UDID provided, use booted simulator
5. **JSON Output Option**: Machine-readable output with `--output` flag
6. **Security**: Never use `shell=True` with user input

### 1. sim_health_check.sh

**Status:** ✅ Implemented

**Purpose:** Verify testing environment is properly configured

**Checks:**
1. macOS (iOS simulators only on macOS)
2. Xcode Command Line Tools
3. simctl availability
4. IDB installation (optional)
5. Python 3
6. Available simulators
7. Booted simulators
8. Python packages (Pillow for visual_diff.py)

**Output:** Colored terminal output with check marks/warnings/errors

**Exit Codes:**
- 0: All required checks passed
- 1: One or more required checks failed

**Design Notes:**
- Uses guard clause pattern: check everything, then summarize
- Provides next steps on success
- Provides fix instructions on failure

### 2. accessibility_audit.py

**Status:** ⏳ Planned

**Purpose:** Scan simulator screen for accessibility compliance issues

**Core Algorithm:**
```python
1. Get accessibility tree: idb ui describe-all --json --nested
2. Parse JSON tree structure
3. Apply WCAG rules:
   - Interactive elements need labels
   - Buttons need descriptive text
   - Complex controls need hints
   - Check hierarchy depth (avoid over-nesting)
   - Verify automation identifiers present
4. Classify issues: critical, warning, info
5. Output structured report
```

**Parameters:**
- `--udid <device-id>`: Target device (optional, uses booted)
- `--output <file>`: Save JSON report to file
- `--verbose`: Include all elements, not just issues
- `--rules <path>`: Custom rules file (advanced)

**Output Format:**
```json
{
  "summary": {
    "timestamp": "2025-10-17T11:20:00Z",
    "device_name": "iPhone 15",
    "total_elements": 45,
    "issues_found": 7,
    "critical": 2,
    "warning": 3,
    "info": 2
  },
  "issues": [
    {
      "severity": "critical",
      "rule": "interactive_element_missing_label",
      "element": {
        "type": "Button",
        "frame": {"x": 200, "y": 400, "width": 120, "height": 44},
        "text": "",
        "label": null
      },
      "issue": "Interactive button missing accessibility label",
      "recommendation": "Add accessibilityLabel property with descriptive text",
      "wcag_guideline": "WCAG 2.1 - 4.1.2 Name, Role, Value"
    }
  ],
  "elements_checked": 45
}
```

**Dependencies:**
- `idb` command must be available
- Simulator must be booted

**Complexity:** 3/5
- JSON parsing straightforward
- Rule engine needs careful design
- WCAG guidelines require research

### 3. visual_diff.py

**Status:** ⏳ Planned

**Purpose:** Compare screenshots to detect visual changes

**Core Algorithm:**
```python
1. Load baseline and current images (PIL/Pillow)
2. Ensure same dimensions (fail if not)
3. Pixel-by-pixel comparison
4. Calculate difference percentage
5. Generate diff image (highlight changed regions)
6. Generate side-by-side comparison
7. Determine pass/fail based on threshold
8. Output structured report
```

**Parameters:**
- `baseline <path>`: Path to baseline screenshot
- `current <path>`: Path to current screenshot
- `--output <dir>`: Output directory for diff artifacts
- `--threshold <float>`: Acceptable difference ratio (default: 0.01 = 1%)
- `--ignore-regions <json>`: Regions to exclude (timestamps, ads, etc.)

**Output:**
- `diff.png`: Highlighted differences (red overlay)
- `side-by-side.png`: Baseline vs current comparison
- `diff-report.json`: Structured results

**Output Format:**
```json
{
  "summary": {
    "timestamp": "2025-10-17T11:25:00Z",
    "baseline": "/path/to/baseline.png",
    "current": "/path/to/current.png",
    "threshold": 0.01,
    "passed": false
  },
  "results": {
    "dimensions": {"width": 390, "height": 844},
    "total_pixels": 329160,
    "different_pixels": 5234,
    "difference_percentage": 1.59,
    "verdict": "FAIL"
  },
  "artifacts": {
    "diff_image": "./diff.png",
    "comparison_image": "./side-by-side.png"
  }
}
```

**Dependencies:**
- Python 3
- Pillow (PIL) package

**Complexity:** 2/5
- Image comparison well-understood problem
- Pillow provides all needed functionality
- Threshold logic straightforward

### 4. test_recorder.py

**Status:** ⏳ Planned

**Purpose:** Record test execution with automatic screenshots and documentation

**Core Algorithm:**
```python
1. Initialize test session with name
2. For each step:
   a. Capture screenshot (simctl io booted screenshot)
   b. Capture accessibility tree (idb ui describe-all)
   c. Record timestamp
   d. Store step description
3. On completion:
   a. Generate markdown test report
   b. Bundle all artifacts
   c. Create summary
```

**Usage Pattern:**
```python
from scripts.test_recorder import TestRecorder

recorder = TestRecorder("Login Flow Test", output_dir="test-artifacts/")

recorder.step("Launch app")
# ... test actions ...

recorder.step("Enter credentials", metadata={"username": "testuser"})
# ... more actions ...

recorder.step("Verify logged in", assertion="Home screen visible")
# ... verification ...

report = recorder.generate_report()
print(f"Test report: {report['markdown_path']}")
```

**Output:**
```
test-artifacts/
├── login-flow-test-2025-10-17-11-30-00/
│   ├── report.md                 # Markdown test report
│   ├── screenshots/
│   │   ├── 001-launch-app.png
│   │   ├── 002-enter-credentials.png
│   │   └── 003-verify-logged-in.png
│   ├── accessibility/
│   │   ├── 001-launch-app.json
│   │   ├── 002-enter-credentials.json
│   │   └── 003-verify-logged-in.json
│   └── metadata.json             # Test execution metadata
```

**report.md Format:**
```markdown
# Test Report: Login Flow Test

**Date:** 2025-10-17 11:30:00
**Status:** PASSED
**Duration:** 12.5 seconds

## Test Steps

### Step 1: Launch app (0.0s)
![Screenshot](screenshots/001-launch-app.png)

**Accessibility Elements:** 15 interactive elements detected

---

### Step 2: Enter credentials (5.2s)
![Screenshot](screenshots/002-enter-credentials.png)

**Metadata:**
- Username: testuser

**Accessibility Elements:** 8 interactive elements detected

---

### Step 3: Verify logged in (10.8s)
![Screenshot](screenshots/003-verify-logged-in.png)

**Assertion:** Home screen visible ✓

**Accessibility Elements:** 23 interactive elements detected

---

## Summary

Total steps: 3
Duration: 12.5s
Screenshots: 3
Accessibility snapshots: 3
```

**Dependencies:**
- `xcrun simctl` for screenshots
- `idb` for accessibility trees
- Python 3

**Complexity:** 3/5
- State management across steps
- File organization
- Markdown generation

### 5. app_state_capture.py

**Status:** ⏳ Planned

**Purpose:** Capture complete app state for debugging

**Core Algorithm:**
```python
1. Capture screenshot
2. Capture accessibility tree
3. Capture recent app logs (xcrun simctl spawn booted log)
4. Capture device info
5. Bundle into timestamped directory
6. Generate summary
```

**Parameters:**
- `--app-bundle-id <id>`: App to capture logs from
- `--output <dir>`: Output directory
- `--log-lines <n>`: Number of log lines to capture (default: 100)
- `--udid <device-id>`: Target device (optional)

**Output:**
```
app-state-2025-10-17-11-35-00/
├── screenshot.png
├── accessibility-tree.json
├── app-logs.txt
├── device-info.json
└── summary.md
```

**Dependencies:**
- `xcrun simctl` for screenshot and logs
- `idb` for accessibility tree
- Python 3

**Complexity:** 2/5
- Combines multiple simple operations
- File organization straightforward

## Reference Documentation Plan

### simctl_reference.md

**Content:**
- Complete command reference extracted from `xcrun simctl help`
- Examples for each command we wrap
- Common patterns and gotchas
- Exit codes and error messages

**Creation Method:**
```bash
# Extract help text
xcrun simctl help > simctl_help.txt
for cmd in boot shutdown launch install io; do
  xcrun simctl $cmd --help >> simctl_help.txt
done

# Manually curate into markdown with examples
```

### idb_reference.md

**Content:**
- Complete command reference extracted from `idb --help`
- Deep dive on `idb ui` commands (our primary use)
- JSON output formats
- Common issues and solutions

**Creation Method:**
```bash
# Extract help text
idb --help > idb_help.txt
idb ui --help >> idb_help.txt
for cmd in tap swipe text describe-all describe-point; do
  idb ui $cmd --help >> idb_help.txt
done

# Manually curate into markdown with examples
```

### accessibility_checklist.md

**Content:**
- WCAG 2.1 guidelines relevant to iOS
- iOS-specific accessibility patterns
- VoiceOver testing guidelines
- Common issues and fixes
- Code examples for developers

**Sources:**
- Apple's Accessibility documentation
- WCAG 2.1 spec (filtered for mobile)
- Community best practices

### common_issues.md

**Content:**
- "Simulator not booting" troubleshooting
- "IDB connection failed" solutions
- "App not launching" debugging steps
- Performance issues
- Known simulator bugs

**Format:**
```markdown
## Issue: Simulator Won't Boot

**Symptoms:**
- `xcrun simctl boot` hangs
- Simulator.app shows blank screen

**Solutions:**
1. Kill existing simulator processes:
   ```bash
   killall Simulator
   ```
2. Reset simulator:
   ```bash
   xcrun simctl erase <device-udid>
   ```
3. Re-create simulator via Xcode
```

### test_patterns.md

**Content:**
- Complete testing workflow examples
- Pattern: Smoke test suite
- Pattern: Visual regression suite
- Pattern: Accessibility audit suite
- Pattern: Performance baseline
- Pattern: Multi-device testing

## Implementation Strategy

### Phase 1: Foundation (Complexity: 2/5)
- ✅ Directory structure
- ✅ SKILL.md
- ✅ CLAUDE.md
- ✅ SPECIFICATION.md (this document)
- ✅ sim_health_check.sh
- ⏳ Extract tool documentation to references/

**Goal:** Solid foundation with environment verification working

### Phase 2: Core Differentiators (Complexity: 4/5)
- ⏳ accessibility_audit.py (highest value, most complex)
- ⏳ accessibility_checklist.md (WCAG patterns)
- ⏳ Test accessibility_audit.py with real simulator

**Goal:** Prove unique value proposition (accessibility-first)

### Phase 3: Visual Testing (Complexity: 2/5)
- ⏳ visual_diff.py (well-understood problem)
- ⏳ Test with actual screenshots
- ⏳ Document usage patterns

**Goal:** Enable regression testing workflow

### Phase 4: Documentation & State (Complexity: 3/5)
- ⏳ test_recorder.py (moderate state management)
- ⏳ app_state_capture.py (simple composition)
- ⏳ test_patterns.md (workflow documentation)
- ⏳ common_issues.md (troubleshooting)

**Goal:** Complete testing toolkit

### Phase 5: Polish & Package (Complexity: 1/5)
- ⏳ examples/login_flow_test.py (complete demonstration)
- ⏳ LICENSE (Apache 2.0)
- ⏳ README.md (distribution guide)
- ⏳ Final testing and validation

**Goal:** Ready for publication

## Design Decisions Log

### Decision 1: Why Not Wrap Every Tool?

**Context:** simctl and idb have 50+ commands combined

**Decision:** Expose 15-20 high-value commands for testing workflows

**Rationale:**
- Jackson's Law: minimal code to solve problem
- Users who need advanced commands can use tools directly
- Reference docs provide path to advanced usage
- Reduces maintenance burden

**Trade-off:** Advanced users might need to drop to raw commands

### Decision 2: Python vs Bash for Scripts

**Context:** Should complex scripts use Python or Bash?

**Decision:**
- Bash for: environment checks, simple wrappers
- Python for: JSON parsing, complex logic, image processing

**Rationale:**
- Bash excellent for system checks and command composition
- Python better for structured data and algorithms
- Both commonly available on macOS
- Type hints in Python aid understanding (CODESTYLE_MAX.md)

### Decision 3: Accessibility Audit Scope

**Context:** Could audit 50+ WCAG guidelines

**Decision:** Focus on 5-10 most impactful iOS-specific patterns

**Rationale:**
- 80/20 rule: most value from core checks
- False positives reduce trust
- Can expand rules in future versions
- Progressive disclosure: advanced rules in references/

### Decision 4: Output Formats

**Context:** Should scripts output JSON, text, or both?

**Decision:** Default to human-readable, `--output` for JSON

**Rationale:**
- Primary user: human developer running ad-hoc tests
- JSON enables automation and integration
- Colored terminal output provides immediate feedback
- Aligns with CODESTYLE_MAX.md token efficiency

### Decision 5: Error Handling Strategy

**Context:** How should scripts handle errors?

**Decision:** Fail fast with actionable messages

**Rationale:**
- CODESTYLE.md: provide actionable error messages
- Testing context: quick feedback loop essential
- Exit code 1 enables CI/CD integration
- Never silently fail (anti-pattern in CODESTYLE.md)

## Security Considerations

### Command Injection Prevention

**Threat:** User-provided paths or IDs could inject shell commands

**Mitigation:**
```python
# ✅ Safe - list arguments
subprocess.run(['idb', 'ui', 'tap', str(x), str(y)])

# ❌ Unsafe - shell interpolation
subprocess.run(f'idb ui tap {x} {y}', shell=True)
```

**Rule:** Never use `shell=True` with user input

### Path Traversal Prevention

**Threat:** User-provided paths could escape intended directories

**Mitigation:**
```python
import pathlib

def validate_output_path(path: str) -> pathlib.Path:
    resolved = pathlib.Path(path).resolve()
    # Ensure within user's home or current directory
    allowed_bases = [pathlib.Path.home(), pathlib.Path.cwd()]
    if not any(str(resolved).startswith(str(base)) for base in allowed_bases):
        raise ValueError(f"Output path not in allowed locations: {path}")
    return resolved
```

### Sensitive Data in Screenshots

**Consideration:** Screenshots may capture sensitive data

**Mitigation:**
- Document in SKILL.md that screenshots may contain sensitive data
- Provide `--output` parameter so users control destination
- Never upload screenshots automatically
- Reference docs explain scrubbing patterns

## Testing Strategy

### Script Testing

Each script needs:
1. **Unit tests**: Core logic without simulator
2. **Integration tests**: With real simulator
3. **Example runs**: Documented in SKILL.md

**Example:**
```bash
# Unit test: JSON parsing without simulator
pytest tests/test_accessibility_audit_parsing.py

# Integration test: Full audit with simulator
# (requires booted simulator)
bash tests/integration/test_accessibility_audit_full.sh

# Manual test: Run and verify output
python scripts/accessibility_audit.py --output test-output.json
cat test-output.json | jq .
```

### Test Fixtures

```
tests/
├── fixtures/
│   ├── accessibility_trees/     # Sample IDB JSON output
│   ├── screenshots/             # Sample images for visual_diff
│   └── logs/                    # Sample app logs
├── unit/
│   ├── test_accessibility_audit.py
│   ├── test_visual_diff.py
│   └── test_test_recorder.py
└── integration/
    ├── test_full_workflow.sh
    └── README.md
```

## Success Metrics

### Completion Criteria

- [ ] All 5 core scripts implemented and tested
- [ ] All 5 reference documents complete
- [ ] 1 complete example (login flow)
- [ ] LICENSE and README present
- [ ] Successfully runs health check on clean macOS
- [ ] Successfully audits real app for accessibility
- [ ] Successfully detects visual differences
- [ ] Documentation references load under 5 seconds

### Quality Criteria

- [ ] Every script has `--help` documentation
- [ ] Every script has actionable error messages
- [ ] Python scripts have type hints
- [ ] Functions under 50 lines (CODESTYLE.md)
- [ ] Files under 300 lines (CODESTYLE.md)
- [ ] Guard clauses used consistently
- [ ] No `shell=True` with user input

### Distribution Criteria

- [ ] Can be cloned and run immediately
- [ ] Works on macOS 12+ with Xcode installed
- [ ] IDB optional but encouraged
- [ ] Clear installation instructions in README.md
- [ ] Ready for GitHub publication

## Future Enhancements (Out of Scope v1.0)

- Multi-device parallel testing
- Video analysis for animation testing
- Integration with CI/CD platforms (GitHub Actions, Jenkins)
- Performance profiling and bottleneck detection
- Network traffic capture and analysis
- Custom rule engines for accessibility/visual testing
- GUI for test recorder
- Integration with test frameworks (XCTest, Detox)

## Appendix: Technology Choices

### Why PIL/Pillow for Image Processing?

- Standard Python imaging library
- Well-documented and maintained
- Handles all common image formats
- Sufficient for pixel-level comparison
- Lightweight dependency

**Alternatives Considered:**
- OpenCV: Overkill for our needs, large dependency
- scikit-image: More complex API, heavier
- ImageMagick: External binary, installation complexity

### Why JSON for Structured Output?

- Universal format, easy to parse
- Human-readable with `jq`
- Type-safe with Python's json module
- Enables tooling integration

**Alternatives Considered:**
- YAML: Less standard for programmatic output
- XML: Verbose, harder to work with
- Plain text: No structure, hard to parse

### Why Markdown for Reports?

- GitHub renders it beautifully
- Human-readable as plain text
- Easy to generate programmatically
- Supports code blocks and images

**Alternatives Considered:**
- HTML: Harder to read as plain text
- PDF: Requires complex generation library
- Plain text: No formatting, no images

---

**Next Steps:** Extract tool documentation, then implement accessibility_audit.py as proof of value.
