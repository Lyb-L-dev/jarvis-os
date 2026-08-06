#!/bin/sh
set -eu

export N8N_ENCRYPTION_KEY="$(cat /run/secrets/n8n_encryption_key)"
workflow_marker="/home/node/.n8n/.jarvis-workflows-${JARVIS_N8N_WORKFLOW_VERSION}"

if [ ! -f "$workflow_marker" ]; then
  n8n start &
  n8n_pid=$!
  trap 'kill "$n8n_pid" 2>/dev/null || true' INT TERM EXIT
  node /opt/jarvis/bootstrap.js
  touch "$workflow_marker"
  wait "$n8n_pid"
  exit $?
fi

exec n8n start
