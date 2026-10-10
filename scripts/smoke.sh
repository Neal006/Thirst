#!/usr/bin/env bash
# Smoke check of a deployed Thirst API (plan 05.12). Exits non-zero if any check fails.
#
#   bash scripts/smoke.sh "$API"                     # API = the ApiUrl stack output
#   ORIGIN=https://main.xxxx.amplifyapp.com bash scripts/smoke.sh "$API"
#
# Checks: GET /assumptions 200, POST /plan 200, GET /leaderboard 200, and an OPTIONS preflight
# that allows ORIGIN exactly (a "*" answer fails: the API must not allow every site).
set -u

if [ $# -ne 1 ] || [ -z "$1" ]; then
  echo "usage: smoke.sh <ApiUrl>" >&2
  exit 2
fi
API="${1%/}"
ORIGIN="${ORIGIN:-http://localhost:5173}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
failed=0

pass() { echo "PASS $1"; }
fail() { echo "FAIL $1: $2"; failed=1; }

# status_of <label> <expected> <curl args...>: runs curl, compares the HTTP status.
status_of() {
  local label=$1 expected=$2 code
  shift 2
  code=$(curl -s -o "$WORK/body" -w '%{http_code}' --max-time 25 "$@") || code=000
  if [ "$code" = "$expected" ]; then
    pass "$label ($code)"
  else
    fail "$label" "expected $expected, got $code"
  fi
}

# A deadline 30 hours from now, written in IST (+05:30) with GNU date.
epoch=$(( $(date +%s) + 30 * 3600 + 19800 ))
deadline=$(date -u -d "@$epoch" +%Y-%m-%dT%H:%M:%S+05:30)
plan_body=$(printf '{"city":"Chennai","cooling":"room_ac","gpu_model":"RTX-4090","gpu_count":2,"work_hours":4,"deadline":"%s","pausable":false,"alpha":0.5}' "$deadline")

status_of assumptions 200 "$API/assumptions"
status_of plan 200 -X POST -H 'content-type: application/json' --data "$plan_body" "$API/plan"
status_of leaderboard 200 "$API/leaderboard?division=D1"

# CORS: a preflight from ORIGIN must come back 2xx and allow exactly that origin.
headers=$(curl -s -D - -o /dev/null --max-time 25 -X OPTIONS \
  -H "Origin: $ORIGIN" -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type' "$API/plan" | tr -d '\r') || headers=""
code=$(printf '%s\n' "$headers" | head -n 1 | awk '{print $2}')
allowed=$(printf '%s\n' "$headers" | grep -i '^access-control-allow-origin:' | head -n 1 \
  | sed 's/^[^:]*:[[:space:]]*//')
case "$code" in
  2??)
    if [ "$allowed" = "$ORIGIN" ]; then
      pass "cors ($ORIGIN)"
    else
      fail cors "origin $ORIGIN not allowed (got '${allowed:-none}')"
    fi
    ;;
  *) fail cors "preflight status ${code:-none}" ;;
esac

if [ "$failed" -ne 0 ]; then
  echo "SMOKE FAILED for $API"
  exit 1
fi
echo "SMOKE OK for $API"
