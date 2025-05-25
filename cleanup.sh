#!/bin/bash
set -e

# Discovery Project Cleanup Script
echo "=== Discovery Project Cleanup ==="
echo "Removing unnecessary logs, caches, and temporary files..."

# 1. Remove any remaining log files (logs now disabled)
echo "Cleaning any remaining log files..."
find . -type f -name "*.log" -not -path "*/\.*" -delete
find . -type f -name "*.log.*" -not -path "*/\.*" -delete
# Remove log directories since they're no longer needed
rm -rf data/logs
rm -rf discovery/data/logs
mkdir -p data
mkdir -p discovery/data

# 2. Remove build artifacts
echo "Cleaning build artifacts..."
rm -rf discovery/build/
rm -rf discovery/discovery.egg-info/
find . -type d -name "__pycache__" -exec rm -rf {} +

# 3. Remove cache directories and contents
echo "Cleaning caches..."
find discovery/data -path "*/cache/*" -type f -delete
find discovery/data -path "*/dev_cache/*" -type f -delete
find discovery/data -path "*/prod_cache/*" -type f -delete
find discovery/data -path "*/staging_cache/*" -type f -delete

# 4. Remove temporary JSON output files
echo "Cleaning output files..."
rm -f discovery/quick.json
rm -f discovery/multi_output.json
rm -f discovery/statuses.json
rm -f discovery/visual.json
rm -f output/*.json

# 5. Remove log directories if they exist
echo "Removing log directories..."
rm -rf data/logs 2>/dev/null || true
rm -rf discovery/data/logs 2>/dev/null || true

echo ""
echo "Cleanup complete! Your project is now tidier."
echo ""
echo "Note: To keep your project clean in the future, consider adding these patterns"
echo "to your .gitignore and periodically running this cleanup script."
