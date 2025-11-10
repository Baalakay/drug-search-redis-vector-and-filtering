#!/bin/bash
# Auto-fix script permissions to prevent execution errors
chmod +x "$0" 2>/dev/null || true

PROJECT_ROOT="$(pwd)"
ACTIVE_PROJECT="$(basename "$PROJECT_ROOT")"
WORKSPACE_NAME="$ACTIVE_PROJECT"  # Dynamic workspace name for fallbacks
ENV_FILE=".devcontainer/.env"

# Ensure .devcontainer exists
if [ ! -d ".devcontainer" ]; then
  echo "Error: .devcontainer directory not found in project root."
  exit 1
fi

# Create .env if it doesn't exist
touch "$ENV_FILE"

# Update or add PROJECT_ROOT
if grep -q "^PROJECT_ROOT=" "$ENV_FILE"; then
  # Use Linux-compatible sed syntax
  sed -i "s|^PROJECT_ROOT=.*$|PROJECT_ROOT=$PROJECT_ROOT|" "$ENV_FILE"
else
  echo "PROJECT_ROOT=$PROJECT_ROOT" >> "$ENV_FILE"
fi

# Update or add ACTIVE_PROJECT
if grep -q "^ACTIVE_PROJECT=" "$ENV_FILE"; then
  # Use Linux-compatible sed syntax
  sed -i "s|^ACTIVE_PROJECT=.*$|ACTIVE_PROJECT=$ACTIVE_PROJECT|" "$ENV_FILE"
else
  echo "ACTIVE_PROJECT=$ACTIVE_PROJECT" >> "$ENV_FILE"
fi

# Update or add WORKSPACE_NAME (for dynamic fallbacks)
if grep -q "^WORKSPACE_NAME=" "$ENV_FILE"; then
  sed -i "s|^WORKSPACE_NAME=.*$|WORKSPACE_NAME=$WORKSPACE_NAME|" "$ENV_FILE"
else
  echo "WORKSPACE_NAME=$WORKSPACE_NAME" >> "$ENV_FILE"
fi

echo "Set PROJECT_ROOT=$PROJECT_ROOT, ACTIVE_PROJECT=$ACTIVE_PROJECT, and WORKSPACE_NAME=$WORKSPACE_NAME in $ENV_FILE
"
