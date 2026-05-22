#!/usr/bin/env bash
# HangBuster end-to-end smoke. Walks through every subcommand and verifies the
# token-budget contract, legacy backward compat, and graceful behaviour when a
# session has no hangs. Designed to be run by hand from the repo root.
#
# Usage:
#   tests/manual/hangbuster_smoke.sh                  # uses booted simulator
#   tests/manual/hangbuster_smoke.sh "iPhone 15"      # boots a specific device
#   IOS_SIM_HANG_MIN_MS=100 tests/manual/hangbuster_smoke.sh
#
# What it checks:
#   1. --help renders without error
#   2. Empty session: --start → immediate --stop produces a clean "no hangs" line
#   3. Real session: --start, 10s capture, --stop emits ~5-line L1 summary
#   4. --get-details (L2) and --get-details --cluster 1 (L3) drill
#   5. --budget-tokens 30 collapses to L0 one-line
#   6. --json output parses
#   7. --diff between two sessions emits a verdict line
#   8. --list-sessions / --clear-sessions --older-than
#   9. Legacy --watch --duration 3 still works

set -euo pipefail

SCRIPT="ios-simulator-skill/skills/ios-simulator-skill/scripts/hang_watcher.py"
DEVICE="${1:-}"
PASS=0
FAIL=0

if [[ ! -f "$SCRIPT" ]]; then
  echo "error: run this from the repo root (couldn't find $SCRIPT)" >&2
  exit 1
fi

# === HELPERS ===

step() {
  printf "\n\033[1;34m▸ %s\033[0m\n" "$*"
}

check() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    printf "  \033[1;32m✓\033[0m %s\n" "$label"
    PASS=$((PASS + 1))
  else
    printf "  \033[1;31m✗\033[0m %s\n" "$label"
    FAIL=$((FAIL + 1))
  fi
}

assert_contains() {
  local label="$1" needle="$2" haystack="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    printf "  \033[1;32m✓\033[0m %s\n" "$label"
    PASS=$((PASS + 1))
  else
    printf "  \033[1;31m✗\033[0m %s — expected substring %q\n     got: %s\n" \
      "$label" "$needle" "$(printf '%s' "$haystack" | head -c 200)"
    FAIL=$((FAIL + 1))
  fi
}

assert_token_budget() {
  local label="$1" budget="$2" text="$3"
  local actual=$(( ${#text} / 4 ))
  if (( actual <= budget )); then
    printf "  \033[1;32m✓\033[0m %s (%d ≤ %d tokens)\n" "$label" "$actual" "$budget"
    PASS=$((PASS + 1))
  else
    printf "  \033[1;31m✗\033[0m %s (%d > %d tokens)\n" "$label" "$actual" "$budget"
    FAIL=$((FAIL + 1))
  fi
}

# === BOOT (if requested) ===

step "Simulator preflight"
if [[ -n "$DEVICE" ]]; then
  echo "  Booting $DEVICE..."
  xcrun simctl boot "$DEVICE" 2>/dev/null || true
fi
BOOTED=$(xcrun simctl list devices booted 2>/dev/null | grep -c Booted || true)
if (( BOOTED == 0 )); then
  echo "  ⚠ No simulator booted. Some checks will be skipped."
  HAS_SIM=0
else
  echo "  ✓ Booted simulator(s): $BOOTED"
  HAS_SIM=1
fi

# === 1. --help ===

step "Help text"
HELP=$(python "$SCRIPT" --help)
assert_contains "Help mentions HangBuster session mode" "HangBuster session mode" "$HELP"
assert_contains "Help lists --start" "--start" "$HELP"
assert_contains "Help lists --diff" "--diff" "$HELP"
assert_contains "Help lists --watch (legacy)" "Legacy live stream" "$HELP"
assert_contains "Help documents env vars" "IOS_SIM_HANG_MIN_MS" "$HELP"

# === 2. Empty session ===

if (( HAS_SIM == 1 )); then
  step "Empty session: --start → immediate --stop"
  SID_EMPTY=$(python "$SCRIPT" --start --min-hang-ms 999999)  # threshold so high nothing matches
  echo "  Session: $SID_EMPTY"
  sleep 1
  EMPTY_OUT=$(python "$SCRIPT" --stop "$SID_EMPTY")
  echo "  Output:"
  printf '%s\n' "$EMPTY_OUT" | sed 's/^/    /'
  assert_contains "Empty session emits 'no hangs' line" "no hangs" "$EMPTY_OUT"
  assert_token_budget "Empty L1 ≤ 200 tokens" 200 "$EMPTY_OUT"
else
  step "Empty session: SKIPPED (no booted simulator)"
fi

# === 3. Real session ===

if (( HAS_SIM == 1 )); then
  step "Real session: 10s capture"
  SID=$(python "$SCRIPT" --start --min-hang-ms "${IOS_SIM_HANG_MIN_MS:-200}")
  echo "  Session: $SID"
  echo "  Interacting (sleep 10)... feel free to drive the simulator while this runs"
  sleep 10
  REAL_OUT=$(python "$SCRIPT" --stop "$SID")
  echo "  Output:"
  printf '%s\n' "$REAL_OUT" | sed 's/^/    /'
  assert_contains "L1 references session ID" "$SID" "$REAL_OUT"
  assert_contains "L1 includes drill hint" "Drill:" "$REAL_OUT"
  assert_token_budget "Default L1 ≤ 200 tokens" 200 "$REAL_OUT"

  # === 4. Drill ===
  step "Drill: --get-details (L2)"
  L2_OUT=$(python "$SCRIPT" --get-details "$SID")
  assert_token_budget "L2 ≤ 2000 tokens" 2000 "$L2_OUT"
  # Only sensible to drill into cluster 1 if there's at least one cluster.
  if [[ "$REAL_OUT" != *"no hangs"* ]]; then
    step "Drill: --get-details --cluster 1 (L3)"
    L3_OUT=$(python "$SCRIPT" --get-details "$SID" --cluster 1)
    assert_contains "L3 carries fingerprint=" "fingerprint=" "$L3_OUT"
    assert_token_budget "L3 ≤ 2000 tokens" 2000 "$L3_OUT"
  fi

  # === 5. Budget collapse ===
  step "Budget: --budget-tokens 30 collapses to L0"
  L0_OUT=$(python "$SCRIPT" --stop "$SID" --budget-tokens 30 2>&1 || true)
  # NOTE: --stop is idempotent re. running a second time after the worker exits;
  # we re-call here just to exercise the formatter path with a tight budget.
  # If the prior --stop wiped the session, generate a fresh empty one.
  if [[ "$L0_OUT" == *"No meta.json"* ]]; then
    SID2=$(python "$SCRIPT" --start --min-hang-ms 999999)
    sleep 1
    L0_OUT=$(python "$SCRIPT" --stop "$SID2" --budget-tokens 30)
  fi
  # L0 has no newline.
  if [[ "$L0_OUT" != *$'\n'* ]]; then
    printf "  \033[1;32m✓\033[0m L0 output is single-line\n"
    PASS=$((PASS + 1))
  else
    printf "  \033[1;31m✗\033[0m L0 output should be single-line; got:\n%s\n" "$L0_OUT"
    FAIL=$((FAIL + 1))
  fi
  assert_token_budget "L0 ≤ 30 tokens" 30 "$L0_OUT"

  # === 6. JSON output ===
  step "JSON: --get-details --json parses"
  JSON_OUT=$(python "$SCRIPT" --get-details "$SID" --json)
  if printf '%s' "$JSON_OUT" | python -c "import json,sys; json.loads(sys.stdin.read())"; then
    printf "  \033[1;32m✓\033[0m JSON output parses\n"
    PASS=$((PASS + 1))
  else
    printf "  \033[1;31m✗\033[0m JSON output did not parse\n"
    FAIL=$((FAIL + 1))
  fi
else
  step "Real session / drill / budget / JSON: SKIPPED (no booted simulator)"
fi

# === 7. Diff ===

if (( HAS_SIM == 1 )); then
  step "Diff: two sessions"
  SID_A=$(python "$SCRIPT" --start --min-hang-ms 999999)
  sleep 1
  python "$SCRIPT" --stop "$SID_A" >/dev/null
  SID_B=$(python "$SCRIPT" --start --min-hang-ms 999999)
  sleep 1
  python "$SCRIPT" --stop "$SID_B" >/dev/null
  DIFF_OUT=$(python "$SCRIPT" --diff "$SID_A" "$SID_B")
  echo "  Output:"
  printf '%s\n' "$DIFF_OUT" | sed 's/^/    /'
  assert_contains "Diff references both sessions" "$SID_A" "$DIFF_OUT"
  assert_contains "Diff references session B" "$SID_B" "$DIFF_OUT"
  assert_contains "Diff includes verdict line" "no change" "$DIFF_OUT"
else
  step "Diff: SKIPPED (no booted simulator)"
fi

# === 8. List / clear ===

step "List + clear"
LIST_OUT=$(python "$SCRIPT" --list-sessions)
echo "  --list-sessions:"
printf '%s\n' "$LIST_OUT" | sed 's/^/    /' | head -10
CLEAR_OUT=$(python "$SCRIPT" --clear-sessions --older-than 0s --json)
assert_contains "--clear-sessions reports JSON" "deleted" "$CLEAR_OUT"

# === 9. Legacy backward compat ===

if (( HAS_SIM == 1 )); then
  step "Legacy: --watch --duration 3"
  # --watch exits after duration; we just need it to run + exit 0.
  if python "$SCRIPT" --watch --duration 3 >/dev/null 2>&1; then
    printf "  \033[1;32m✓\033[0m Legacy --watch exits cleanly\n"
    PASS=$((PASS + 1))
  else
    printf "  \033[1;31m✗\033[0m Legacy --watch crashed\n"
    FAIL=$((FAIL + 1))
  fi
else
  step "Legacy --watch: SKIPPED (no booted simulator)"
fi

# === SUMMARY ===

step "Summary"
printf "  Passed: %d\n  Failed: %d\n" "$PASS" "$FAIL"
if (( FAIL > 0 )); then
  exit 1
fi
echo "  All checks passed."
