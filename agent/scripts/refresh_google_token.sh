#!/usr/bin/env bash
# Sign in to Google again and push the new token to the deployed agent.
# Needed every 7 days while the OAuth app is in testing mode.
set -euo pipefail
cd "$(dirname "$0")/.."

rm -f token.json
uv run python calendar_client.py  # opens a browser to sign in

set -a
source <(grep '^LIVEKIT_' .env.local)
set +a

umask 077
secrets="$(mktemp)"
trap 'rm -f "$secrets"' EXIT
printf 'GOOGLE_TOKEN_JSON=%s\n' "$(tr -d '\n' < token.json)" > "$secrets"
lk agent update-secrets --secrets-file "$secrets"
echo "Token updated; the agent restarts with it."
