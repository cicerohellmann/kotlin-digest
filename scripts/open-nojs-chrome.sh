#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAGE="${1:-site/index.html}"
PROFILE="${KOTLIN_DIGEST_NOJS_PROFILE:-/tmp/kotlin-digest-nojs-chrome}"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"

if [[ ! -x "$CHROME" ]]; then
  echo "Google Chrome was not found at: $CHROME" >&2
  echo "Set CHROME=/path/to/chrome and rerun this script." >&2
  exit 1
fi

mkdir -p "$PROFILE/Default"
cat > "$PROFILE/Default/Preferences" <<'JSON'
{
  "browser": {
    "has_seen_welcome_page": true
  },
  "profile": {
    "default_content_setting_values": {
      "javascript": 2
    },
    "managed_default_content_settings": {
      "javascript": 2
    }
  },
  "session": {
    "restore_on_startup": 5
  }
}
JSON

if [[ "$PAGE" =~ ^https?:// || "$PAGE" =~ ^file:// ]]; then
  URL="$PAGE"
else
  URL="file://$ROOT/$PAGE"
fi

exec "$CHROME" \
  --user-data-dir="$PROFILE" \
  --no-first-run \
  --no-default-browser-check \
  --disable-features=Translate \
  --new-window "$URL"
