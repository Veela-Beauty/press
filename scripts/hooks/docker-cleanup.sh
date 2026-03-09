#!/bin/bash
# /etc/cron.daily/press-docker-cleanup
# OR run manually before a deploy when "port already allocated" errors occur.
#
# PURPOSE: Remove stopped Docker containers that hold allocated ports.
#          Failed deploys leave containers in "Exited" state. Next deploy fails
#          with "port already allocated" because the old container still owns the port.
#
# DEPLOY (run on each app server):
#   cp docker-cleanup.sh /etc/cron.daily/press-docker-cleanup
#   chmod +x /etc/cron.daily/press-docker-cleanup
#
# SAFE: Only removes stopped/exited containers. Never touches running containers.

set -e

# Remove ALL stopped/exited containers — not just old ones.
# Port-allocation failures happen immediately after a failed deploy (seconds, not hours).
# The --filter "until=24h" would miss those. Running containers are never affected.
REMOVED=$(docker container prune -f 2>&1)

# Only dangling images (no tag, no reference). Tagged images are never removed.
IMAGES=$(docker image prune -f 2>&1)

echo "[$(date)] Docker cleanup complete"
echo "Containers removed: ${REMOVED}"
echo "Images removed: ${IMAGES}"
