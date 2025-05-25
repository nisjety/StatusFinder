#!/bin/bash
set -e

# Configuration
PROJECT="discovery"
SCRAPYD_URL="http://localhost:6800"
USERNAME="admin"
PASSWORD="scrapyd"

echo "Deploying project $PROJECT to Scrapyd at $SCRAPYD_URL..."
cd /app

# Build egg file
python setup.py bdist_egg || { echo "Failed to build egg"; exit 1; }

# Find the egg file
EGG_FILE=$(find dist -name "*.egg" | sort -V | tail -1)
if [ -z "$EGG_FILE" ]; then
  echo "No egg file found in dist directory"
  exit 1
fi

echo "Using egg file: $EGG_FILE"

# Upload egg to Scrapyd
RESPONSE=$(curl -s -u "$USERNAME:$PASSWORD" "$SCRAPYD_URL/addversion.json" \
  -F project=$PROJECT \
  -F version=$(date +%Y%m%d-%H%M%S) \
  -F egg=@$EGG_FILE)

echo "Response: $RESPONSE"

# Check response
if echo "$RESPONSE" | grep -q '"status": "ok"'; then
  echo "✅ Deployment successful!"
  
  # List available spiders
  echo "Available spiders:"
  # Print discovered spiders from egg
  python3 -c '
from importlib import import_module
from inspect import isclass
module = import_module("discovery.spiders")
found = []
for item in dir(module):
    obj = getattr(module, item)
    if isclass(obj) and hasattr(obj, "name"):
        found.append(obj.name)
print("Found in egg:", sorted(found))
'

  # Print spiders from Scrapyd
  echo "Found in Scrapyd:"
  curl -s -u "$USERNAME:$PASSWORD" "$SCRAPYD_URL/listspiders.json?project=$PROJECT" | python -m json.tool
else
  echo "❌ Deployment failed: $RESPONSE"
  exit 1
fi
