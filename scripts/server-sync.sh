#!/usr/bin/env bash
# Deploy forge-api and (optionally) build the forge-eval Docker image.
#
# Usage:
#   ./server-sync.sh                        # update forge-api only
#   ./server-sync.sh /path/to/forge         # also build forge-eval image
#
# Run this from the forge-api repo root on ventura-nanoclaw.
# Requires: git, pm2, python3 (optional: docker)

set -euo pipefail

FORGE_REPO="${1:-}"

echo "=== forge-api: pulling latest ==="
git pull

echo "=== forge-api: restarting via PM2 ==="
pm2 restart forge-api

echo "=== forge-api: seeding round spec files ==="
# Copy spec JSON files from a sibling forge repo clone if it exists.
SIBLING_FORGE="$(dirname "$(pwd)")/forge"
if [ -d "$SIBLING_FORGE/specs" ]; then
  mkdir -p data/specs
  cp -r "$SIBLING_FORGE/specs/"* data/specs/
  echo "  Copied specs from $SIBLING_FORGE"
elif [ -n "$FORGE_REPO" ] && [ -d "$FORGE_REPO/specs" ]; then
  mkdir -p data/specs
  cp -r "$FORGE_REPO/specs/"* data/specs/
  echo "  Copied specs from $FORGE_REPO"
else
  echo "  No forge repo found for spec sync — skipping (set \$1 to forge path)"
fi

if [ -n "$FORGE_REPO" ]; then
  echo "=== forge-eval: building Docker image from $FORGE_REPO ==="
  (cd "$FORGE_REPO" && git pull && docker build -t forge-eval .)
  echo "  forge-eval image built."
else
  echo "=== forge-eval: skipping Docker build (pass forge repo path to build) ==="
fi

echo ""
echo "Done. forge-api is live on port 8000."
echo "Health: curl http://localhost:8000/health"
