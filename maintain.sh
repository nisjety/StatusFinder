#!/bin/bash
#
# Discovery Project Maintenance Script
# 
# This script performs regular maintenance tasks:
# 1. Clean up old logs and temporary files
# 2. Optimize cache directories
# 3. Run tests to ensure everything still works
#
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

echo "=== Discovery Project Maintenance ==="
echo "Starting maintenance at: $(date)"
echo ""

# 1. Remove any log files that might have been created
echo "Removing any log files (logging to files is disabled)..."
find . -type f -name "*.log" -not -path "*/\.*" -delete
find . -type f -name "*.log.*" -not -path "*/\.*" -delete

# 2. Remove stale cache files (older than 30 days)
echo "Cleaning stale cache files..."
find discovery/data -path "*/cache/*" -type f -mtime +30 -delete
find discovery/data -path "*/dev_cache/*" -type f -mtime +30 -delete
find discovery/data -path "*/prod_cache/*" -type f -mtime +30 -delete
find discovery/data -path "*/staging_cache/*" -type f -mtime +30 -delete

# 3. Remove log directories if they exist
echo "Removing log directories (no longer needed)..."
rm -rf data/logs 2>/dev/null || true
rm -rf discovery/data/logs 2>/dev/null || true

# 4. Run tests to verify everything still works
echo "Running tests to verify system integrity..."
cd discovery
python -m pytest -xvs tests/ || echo "⚠️ Some tests failed. Please review the output."

echo ""
echo "Maintenance completed at: $(date)"
echo "To keep your project running smoothly, run this script periodically."
