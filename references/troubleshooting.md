# Troubleshooting

## Problem → Solution Format

### Simulator won't boot
**Fix:** `killall Simulator && xcrun simctl erase <udid>`

### IDB not connecting
**Fix:** `idb kill && idb companion --boot-status-check`

### App won't launch
**Fix:** `xcrun simctl terminate booted <bundle-id> && xcrun simctl launch booted <bundle-id>`

### Screenshot fails
**Fix:** Ensure simulator booted: `xcrun simctl boot <udid>`

### "No booted devices"
**Fix:** `open -a Simulator` or `xcrun simctl boot <udid>`

### IDB "Target not found"
**Fix:** `idb list-targets` to verify UDID

### Permission denied
**Fix:** `chmod +x scripts/*.sh`

### Python module not found
**Fix:** `pip3 install pillow` (for visual_diff.py)

### Accessibility tree empty
**Fix:** App must be in foreground: `xcrun simctl launch booted <bundle-id>`

### Video recording hangs
**Fix:** Ctrl+C to stop recording, file saves on interrupt

### Logs not showing
**Fix:** Use correct app name: `xcrun simctl spawn booted log stream --predicate 'process == "AppName"'`

### Device storage full
**Fix:** `xcrun simctl erase <udid>` (warning: deletes all data)

## Quick Diagnostics

```bash
# Check simulator state
xcrun simctl list devices | grep Booted

# Verify IDB connection
idb list-targets

# Test basic interaction
xcrun simctl io booted screenshot test.png
```