#!/bin/sh
set -eu
if [ "$(id -u)" = "0" ]; then
    # Render mounts the persistent disk before startup. Prepare only app state.
    mkdir -p "${GCE_STATE_DIR:-/var/data/gce}"
    chown -R gce:gce "${GCE_STATE_DIR:-/var/data/gce}"
    exec gosu gce python /app/scripts/serve.py
fi
exec python /app/scripts/serve.py
