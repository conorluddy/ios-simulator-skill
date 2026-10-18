#!/usr/bin/env bash
# idb 1.7 end-to-end smoke. Drives Settings through the real scripts and checks
# each idb 1.7 feature by its effect where one is observable. Run by hand from the
# repo root; not wired into CI (CI has no simulator).
#
# Usage:
#   tests/manual/idb17_smoke.sh                                  # throwaway sim (default)
#   tests/manual/idb17_smoke.sh --udid <UDID> --yes              # an existing sim
#   tests/manual/idb17_smoke.sh --udid <UDID> --yes --app <id>   # also map an app's screen
#
# By default it creates, boots and deletes its own simulator, so nothing of yours is
# touched. Against an existing sim it empties the photo library (unrecoverable) and
# flips settings it then restores (a keyboard toggle, Increase Contrast, orientation),
# so it refuses without --yes (AGENTS.md Principle 10).

set -uo pipefail

SCRIPTS="ios-simulator-skill/skills/ios-simulator-skill/scripts"
DEVICE_TYPE="${IOS_SIM_SMOKE_DEVICE_TYPE:-com.apple.CoreSimulator.SimDeviceType.iPhone-18-Pro}"
READY_TIMEOUT_SECONDS=30
UDID=""
APP=""
CONFIRMED=false
THROWAWAY=false
PASS=0
FAIL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --udid) UDID="$2"; shift 2 ;;
    --app) APP="$2"; shift 2 ;;
    --yes) CONFIRMED=true; shift ;;
    *) echo "usage: $0 [--udid UDID --yes] [--app BUNDLE_ID]" >&2; exit 2 ;;
  esac
done

if [[ ! -d "$SCRIPTS" ]]; then
  echo "error: run this from the repo root (couldn't find $SCRIPTS)" >&2
  exit 1
fi
if [[ -n "$UDID" && "$CONFIRMED" != true ]]; then
  echo "Refusing to empty the photo library on $UDID without --yes: confirm with the user, then re-run with --yes" >&2
  exit 1
fi
if [[ -n "$APP" && -z "$UDID" ]]; then
  echo "error: --app needs --udid (the throwaway sim has only built-in apps)" >&2
  exit 2
fi

if [[ -z "$UDID" ]]; then
  # Newest available iOS runtime that supports DEVICE_TYPE.
  runtime=$(xcrun simctl list runtimes -j | python3 -c '
import json, sys
device_type = sys.argv[1]
ios = [
    r for r in json.load(sys.stdin)["runtimes"]
    if r["platform"] == "iOS" and r["isAvailable"]
    and any(t["identifier"] == device_type for t in r.get("supportedDeviceTypes", []))
]
print(max(ios, key=lambda r: [int(p) for p in r["version"].split(".")])["identifier"] if ios else "")
' "$DEVICE_TYPE")
  if [[ -z "$runtime" ]]; then
    echo "error: no iOS runtime supports $DEVICE_TYPE (set IOS_SIM_SMOKE_DEVICE_TYPE)" >&2
    exit 1
  fi
  UDID=$(xcrun simctl create "idb17-smoke-$$" "$DEVICE_TYPE" "$runtime") || exit 1
  THROWAWAY=true
  trap 'xcrun simctl delete "$UDID" >/dev/null 2>&1' EXIT
  xcrun simctl boot "$UDID" && xcrun simctl bootstatus "$UDID" -b >/dev/null || exit 1
fi

# === HELPERS ===

step() { printf "\n\033[1;34m▸ %s\033[0m\n" "$*"; }

pass() { printf "  \033[1;32m✓\033[0m %s\n" "$1"; PASS=$((PASS + 1)); }

fail() { printf "  \033[1;31m✗\033[0m %s\n     %s\n" "$1" "${2:-}"; FAIL=$((FAIL + 1)); }

# expect <label> <needle> <command...>: run the command, pass if its output contains needle.
expect() {
  local label="$1" needle="$2"
  shift 2
  local output
  output=$("$@" 2>&1)
  if [[ "$output" == *"$needle"* ]]; then
    pass "$label"
  else
    fail "$label" "expected '$needle', got: $(printf '%s' "$output" | head -c 240)"
  fi
}

run() { python3 "$SCRIPTS/$1" --udid "$UDID" "${@:2}"; }

# ax_value <key> <marker>: AXValue of the first element whose <key> equals marker.
ax_value() {
  idb ui describe-all --udid "$UDID" --json 2>/dev/null | python3 -c '
import json, sys
key, marker = sys.argv[1], sys.argv[2]
print(next((str(e.get("AXValue")) for e in json.load(sys.stdin) if e.get(key) == marker), "missing"))
' "$1" "$2"
}

# element_count [type]: elements in the default read (of that type, if given); 0 on failure.
element_count() {
  idb ui describe-all --udid "$UDID" --json 2>/dev/null | python3 -c '
import json, sys
wanted = sys.argv[1] if len(sys.argv) > 1 else None
print(sum(1 for e in json.load(sys.stdin) if wanted is None or e.get("type") == wanted))
' "$@" 2>/dev/null || echo 0
}

# wait_for_tree [type]: poll until the default read sees a real screen (one with an element
# of that type, if given). A read stuck on a lone zero-size app node after a relaunch
# (facebook/idb#964) is woken by one axbridge read.
wait_for_tree() {
  local deadline=$((SECONDS + READY_TIMEOUT_SECONDS))
  local woke=false
  while (( SECONDS < deadline )); do
    if [[ -n "${1:-}" ]] && (( $(element_count "$1") > 0 )); then return 0; fi
    if [[ -z "${1:-}" ]] && (( $(element_count) > 1 )); then return 0; fi
    if [[ "$woke" == false ]] && (( SECONDS > deadline - READY_TIMEOUT_SECONDS / 2 )); then
      run screen_mapper.py --deep --json >/dev/null 2>&1
      woke=true
    fi
    sleep 1
  done
  echo "  (accessibility tree still empty after ${READY_TIMEOUT_SECONDS}s)" >&2
  return 1
}

open_settings() {
  xcrun simctl terminate "$UDID" com.apple.Preferences 2>/dev/null
  xcrun simctl launch "$UDID" com.apple.Preferences >/dev/null
  sleep 1
  # The root screen's search field is the last thing to appear on a fresh sim.
  wait_for_tree TextField
}

photo_count() {
  find "$HOME/Library/Developer/CoreSimulator/Devices/$UDID/data/Media/DCIM" -type f \
    \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.heic' \) 2>/dev/null | wc -l | tr -d ' '
}

sim_kind=$([[ "$THROWAWAY" == true ]] && echo "throwaway sim" || echo "existing sim")
echo "idb17 smoke on $UDID, $sim_kind ($(brew list --versions idb-cli idb-companion 2>/dev/null | tr '\n' ' '))"

# === SCREEN READS ===

step "screen_mapper: default read and --deep (axbridge)"
open_settings
shallow=$(run screen_mapper.py --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["total_elements"])' 2>/dev/null || echo 0)
deep=$(run screen_mapper.py --deep --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["total_elements"])' 2>/dev/null || echo 0)
if (( shallow > 1 )); then pass "default read sees $shallow elements"; else fail "default read" "only $shallow elements"; fi
if (( deep > shallow )); then pass "--deep sees more ($deep > $shallow)"; else fail "--deep" "$deep vs $shallow"; fi

if [[ -n "$APP" ]]; then
  xcrun simctl launch "$UDID" "$APP" >/dev/null && sleep 1 && wait_for_tree
  expect "screen_mapper maps $APP" "Screen:" run screen_mapper.py
  open_settings
fi

# === NAVIGATOR ===

step "navigator: press, toggle guard, set-value"
expect "press by unique ID" "(accessibility press)" run navigator.py --find-id com.apple.settings.general --tap
sleep 1.5
expect "press by unique label" "(accessibility press)" run navigator.py --find-exact Keyboard --tap
sleep 1.5
before=$(ax_value AXUniqueId KeyboardAllowPaddle)
expect "--expect refuses a mismatched value" "Not tapped" run navigator.py --find-id KeyboardAllowPaddle --tap --expect "x$before"
run navigator.py --find-id KeyboardAllowPaddle --tap --expect "$before" >/dev/null
sleep 1.5
after=$(ax_value AXUniqueId KeyboardAllowPaddle)
if [[ "$after" != "$before" && "$after" != "missing" ]]; then pass "toggle flipped $before -> $after"; else fail "toggle flip" "$before -> $after"; fi
run navigator.py --find-id KeyboardAllowPaddle --tap --expect "$after" >/dev/null
sleep 1.5
restored=$(ax_value AXUniqueId KeyboardAllowPaddle)
if [[ "$restored" == "$before" ]]; then pass "toggle restored to $before"; else fail "toggle restore" "now $restored, was $before"; fi

open_settings
expect "--set-value reports the value read back" "Set value of" run navigator.py --find-type TextField --set-value "Zürich ☕"
value=$(ax_value type TextField)
if [[ "$value" == "Zürich ☕" ]]; then pass "field holds the non-ASCII text"; else fail "--set-value" "field holds '$value'"; fi
open_settings

# === GESTURES AND KEYS ===

step "gesture and keyboard primitives"
expect "--rotate landscape-left" "" run gesture.py --rotate landscape-left
sleep 1
rotation=$(idb rotation --udid "$UDID" 2>&1)
if [[ "$rotation" == LANDSCAPE* ]]; then pass "device reports $rotation"; else fail "rotation read-back" "$rotation"; fi
run gesture.py --rotate portrait >/dev/null 2>&1
if run gesture.py --double-tap 30,30 >/dev/null 2>&1; then pass "--double-tap accepted"; else fail "--double-tap" "non-zero exit"; fi
if run gesture.py --shake >/dev/null 2>&1; then pass "--shake accepted"; else fail "--shake" "non-zero exit"; fi
if run keyboard.py --key a --shift >/dev/null 2>&1; then pass "--key a --shift accepted"; else fail "--shift" "non-zero exit"; fi

# === DEVICE STATE ===

step "appearance --contrast"
run appearance.py --contrast high >/dev/null 2>&1
state=$(xcrun simctl ui "$UDID" increase_contrast 2>&1)
if [[ "$state" == "enabled" ]]; then pass "contrast high -> $state"; else fail "contrast high" "$state"; fi
run appearance.py --contrast normal >/dev/null 2>&1
state=$(xcrun simctl ui "$UDID" increase_contrast 2>&1)
if [[ "$state" == "disabled" ]]; then pass "contrast normal -> $state"; else fail "contrast normal" "$state"; fi

step "push_notification --list / --clear"
# A push sent while its app is frontmost isn't delivered to Notification Center.
xcrun simctl launch "$UDID" com.apple.mobilecal >/dev/null
sleep 2
run push_notification.py --bundle-id com.apple.Preferences --title Smoke --body One >/dev/null 2>&1
# Delivery takes a few seconds on a fresh sim.
for _ in {1..10}; do
  [[ "$(run push_notification.py --bundle-id com.apple.Preferences --list 2>&1)" == *Smoke* ]] && break
  sleep 1
done
expect "--list shows the notification" "Smoke" run push_notification.py --bundle-id com.apple.Preferences --list
run push_notification.py --bundle-id com.apple.Preferences --clear >/dev/null 2>&1
expect "--clear empties the list" "0 notification" run push_notification.py --bundle-id com.apple.Preferences --list

step "media --add / --clear"
image="${TMPDIR:-/tmp}/idb17_smoke.png"
python3 -c 'import base64,sys; open(sys.argv[1],"wb").write(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))' "$image"
run media.py --clear --yes --add "$image" >/dev/null 2>&1
sleep 2
count=$(photo_count)
if (( count >= 1 )); then pass "--clear --add left $count photo(s)"; else fail "media --add" "$count photos"; fi
run media.py --clear --yes >/dev/null 2>&1
sleep 2
count=$(photo_count)
if (( count == 0 )); then pass "--clear emptied the library"; else fail "media --clear" "$count photos left"; fi
rm -f "$image"

# === SUMMARY ===

printf "\n%d passed, %d failed\n" "$PASS" "$FAIL"
(( FAIL == 0 ))
