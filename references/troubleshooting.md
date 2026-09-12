# Troubleshooting

## Problem → Solution Format

### Taps/swipes/typing silently do nothing (reads still work)
On Xcode 27, `idb-companion` older than 1.5.1 cannot find `SimulatorKit.framework` — it moved to
`Contents/SharedFrameworks`. HID writes are accepted and dropped, so `idb` logs success while the
screen never changes.
**Fix:** `brew upgrade facebook/fb/idb-companion` (verify with `brew list --versions idb-companion`)

### "SimulatorKit is required for HID interactions"
Same cause as above.
**Fix:** `brew tap facebook/fb && brew install facebook/fb/idb-companion facebook/fb/idb-cli`

### Every idb call fails with "Connection refused" / "No such file"
A dead companion is still registered in `/tmp/idb/state`, so idb dials its socket instead of
spawning a replacement. Restarting the companion alone does not clear it.
**Fix:** `idb disconnect <udid>`

### "open -a Simulator" fails / no Simulator.app
Xcode 27 replaced `Simulator.app` with `DeviceHub.app` (`Xcode.app/Contents/Applications/`).
Quitting DeviceHub shuts down the simulator it hosts.
**Fix:** `xcrun simctl boot <udid>`

### "idb: command not found"
The CLI and the companion are separate packages.
**Fix:** `brew tap facebook/fb && brew install facebook/fb/idb-companion facebook/fb/idb-cli`

### Simulator won't boot
**Fix:** `xcrun simctl shutdown <udid> && xcrun simctl boot <udid>`
(Last resort, wipes the device: `xcrun simctl erase <udid>`)

### IDB not connecting
**Fix:** `idb kill && idb companion --boot-status-check`
(If taps still do nothing afterwards, this is not the cause — see the Xcode 27 entries above.)

### App won't launch
**Fix:** `xcrun simctl terminate booted <bundle-id> && xcrun simctl launch booted <bundle-id>`

### Screenshot fails
**Fix:** Ensure simulator booted: `xcrun simctl boot <udid>`

### "No booted devices"
**Fix:** `xcrun simctl boot <udid>`

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

Run `bash scripts/sim_health_check.sh` first — it checks versions and known Xcode 27 traps.

```bash
# Check simulator state
xcrun simctl list devices | grep Booted

# Verify IDB connection
idb list-targets

# Test basic interaction
xcrun simctl io booted screenshot test.png
```