# Error Capture Fix - Build and Test Script

## Date
2025-10-18

## Problem
The build_and_test.py script was failing to capture and display Swift compilation errors, reporting "0 errors" even when builds failed with actual compilation errors.

## Root Causes
1. **xcresult format change**: Newer Xcode versions (Xcode 16+) use a different xcresult JSON structure with top-level `errors` and `warnings` arrays instead of the legacy nested `errorSummaries`/`warningSummaries` format
2. **Missing stderr caching**: When using progressive disclosure (`--get-errors`), the stderr wasn't persisted to disk, so errors couldn't be retrieved later
3. **Incomplete fallback parser**: Although a stderr fallback existed, it didn't have regex patterns for Swift compilation errors

## Changes Made

### 1. skill/scripts/xcode/xcresult.py
- **Updated `count_issues()`**: Now checks top-level `errors`/`warnings` arrays first (newer format), then falls back to legacy `actions[0].buildResult.issues` format
- **Updated `get_errors()`**: Added support for top-level errors array and new `_extract_location_from_url()` method
- **Updated `get_warnings()`**: Added support for top-level warnings array
- **Added `_extract_location_from_url()`**: New method to parse sourceURL format used in newer xcresult bundles (e.g., `file:///path/to/file.swift#StartingLineNumber=134&StartingColumnNumber=58&...`)
- **Updated `_parse_stderr_errors()`**: Added Pattern 0 for Swift/Clang compilation errors in stderr (`/path/file.swift:135:59: error: message`)

### 2. skill/scripts/xcode/cache.py
- **Added `save_stderr()`**: Saves stderr output to `~/.ios-simulator-skill/xcresults/{xcresult_id}.stderr`
- **Added `get_stderr()`**: Retrieves cached stderr for progressive disclosure

### 3. skill/scripts/build_and_test.py
- **Added stderr caching**: After builds/tests, saves stderr to cache alongside xcresult bundle
- **Added stderr loading**: When using `--get-errors`/`--get-warnings`/`--get-all`, loads cached stderr and passes to parser

## Benefits
✅ Supports both newer (Xcode 16+) and legacy xcresult formats  
✅ Progressive disclosure now works correctly - errors can be retrieved hours/days after build  
✅ Swift compilation errors are properly captured and displayed with file:line:column information  
✅ Warnings are properly captured from modern xcresult format  
✅ Backwards compatible with older Xcode versions  

## Testing
Verified with deliberate Swift compilation error (`Fosnt` typo instead of `Font`):

**Before fix:**
```
Build: FAILED (0 errors, 0 warnings) [xcresult-abc123]
$ python scripts/build_and_test.py --get-errors xcresult-abc123
No errors found.
```

**After fix:**
```
Build: FAILED (1 errors, 2 warnings) [xcresult-abc123]
$ python scripts/build_and_test.py --get-errors xcresult-abc123
Errors (1):

1. Cannot find 'Fosnt' in scope
   Location: /Users/.../PositionDetailView.swift:line 135
```

## Related Issues
This fix resolves error capture issues when building with Xcode 16+ and enables proper progressive disclosure of build errors.
