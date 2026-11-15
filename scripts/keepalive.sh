#!/usr/bin/env bash
# Keep-alive ping for DukaanPulse on a free host.
#
# Render free web services spin down after ~15 minutes without traffic, and the
# next request pays a 30-60s cold start. Hitting the health endpoint on a fixed
# schedule keeps the service awake.
#
# Usage:
#   ./scripts/keepalive.sh                       # uses the default URL below
#   ./scripts/keepalive.sh https://app.onrender.com
#   BASE_URL=https://app.onrender.com ./scripts/keepalive.sh
#
# Exit code 0 when the health endpoint answers ok, 1 otherwise (so a cron
# service can alert on failure).
set -euo pipefail

BASE_URL="${1:-${BASE_URL:-https://dukaanpulse.onrender.com}}"
URL="${BASE_URL%/}/api/health"

code="$(curl -s -o /tmp/dukaanpulse_keepalive.out -w '%{http_code}' --max-time 60 "$URL" || echo 000)"
body="$(cat /tmp/dukaanpulse_keepalive.out 2>/dev/null || true)"

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) GET $URL -> $code $body"

if [ "$code" != "200" ]; then
  echo "keep-alive: health check did not return 200" >&2
  exit 1
fi
