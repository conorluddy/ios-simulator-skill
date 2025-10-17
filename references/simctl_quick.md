# simctl Quick Reference

## Essential Commands Only

### list devices
**Usage:** `xcrun simctl list devices`
**Output:** Device list with UDIDs and states
**Key:** Use `booted` as UDID for current device

### boot
**Usage:** `xcrun simctl boot <device-udid>`
**Output:** None (success) or error

### launch
**Usage:** `xcrun simctl launch booted <bundle-id>`
**Output:** PID of launched app

### install
**Usage:** `xcrun simctl install booted <app-path>`
**Output:** None (success) or error

### io screenshot
**Usage:** `xcrun simctl io booted screenshot <file.png>`
**Output:** PNG file saved
**Options:** `--type=png|jpeg` (default: png)

### io recordVideo
**Usage:** `xcrun simctl io booted recordVideo <file.mp4>`
**Output:** Video file (Ctrl+C to stop)
**Options:** `--codec=h264|hevc` (default: hevc)

### get_app_container
**Usage:** `xcrun simctl get_app_container booted <bundle-id> data`
**Output:** Path to app's data directory

### spawn log
**Usage:** `xcrun simctl spawn booted log stream --predicate 'process == "<app>"'`
**Output:** Live log stream

## Common Patterns

```bash
# Get booted device UDID
xcrun simctl list devices | grep Booted

# Quick app test
xcrun simctl boot <udid>
xcrun simctl install booted app.app
xcrun simctl launch booted com.example.app
xcrun simctl io booted screenshot test.png
```

## Troubleshooting
See `troubleshooting.md`