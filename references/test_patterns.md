# Test Patterns

## Smoke Test
```bash
xcrun simctl boot <udid>
xcrun simctl launch booted <bundle-id>
python scripts/accessibility_audit.py
xcrun simctl io booted screenshot smoke.png
```

## Visual Regression
```bash
# Baseline
xcrun simctl io booted screenshot baseline.png

# After changes
xcrun simctl io booted screenshot current.png
python scripts/visual_diff.py baseline.png current.png
```

## Full Accessibility Audit
```bash
# Each screen
for screen in home login settings; do
  # Navigate to screen (app-specific)
  python scripts/accessibility_audit.py --output $screen.json
done
```

## Bug Report Capture
```bash
python scripts/app_state_capture.py \
  --app-bundle-id com.example.app \
  --output bug-report/
```

## Multi-Device Test
```bash
for device in "iPhone 15" "iPad Pro"; do
  udid=$(xcrun simctl create test-$device "$device")
  xcrun simctl boot $udid
  xcrun simctl install $udid app.app
  xcrun simctl launch $udid com.example.app
  xcrun simctl io $udid screenshot $device.png
  xcrun simctl delete $udid
done
```

## Performance Baseline
```bash
# Capture initial state
xcrun simctl io booted screenshot perf-before.png
# Run performance test
xcrun simctl launch booted com.example.app
sleep 5
xcrun simctl io booted screenshot perf-after.png
python scripts/visual_diff.py perf-before.png perf-after.png
```

## Login Flow Test
```python
from scripts.test_recorder import TestRecorder

rec = TestRecorder("Login Test")
rec.step("Launch app")
# idb ui tap 200 400  # Login button
rec.step("Enter credentials")
# idb ui text "user@example.com"
rec.step("Submit")
# idb ui tap 200 500
rec.generate_report()
```