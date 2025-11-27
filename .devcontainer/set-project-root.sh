#!/bin/bash
# Auto-fix script permissions to prevent execution errors
chmod +x "$0" 2>/dev/null || true

PROJECT_ROOT="$(pwd)"
RAW_PROJECT_NAME="$(basename "$PROJECT_ROOT")"

# Always use lowercase for docker-friendly names (containers, images, networks)
ACTIVE_PROJECT="$(echo "$RAW_PROJECT_NAME" | tr '[:upper:]' '[:lower:]')"
WORKSPACE_NAME="$ACTIVE_PROJECT"

# Keep original case for file paths (matches devcontainer.json's localWorkspaceFolderBasename)
WORKSPACE_FOLDER_NAME="$RAW_PROJECT_NAME"

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

# Update or add WORKSPACE_NAME (matches ACTIVE_PROJECT)
if grep -q "^WORKSPACE_NAME=" "$ENV_FILE"; then
  sed -i "s|^WORKSPACE_NAME=.*$|WORKSPACE_NAME=$WORKSPACE_NAME|" "$ENV_FILE"
else
  echo "WORKSPACE_NAME=$WORKSPACE_NAME" >> "$ENV_FILE"
fi


# Update or add COMPOSE_PROJECT_NAME (ensures docker-compose uses project-specific names)
COMPOSE_PROJECT_NAME="${ACTIVE_PROJECT}_devcontainer"
if grep -q "^COMPOSE_PROJECT_NAME=" "$ENV_FILE"; then
  sed -i "s|^COMPOSE_PROJECT_NAME=.*$|COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT_NAME|" "$ENV_FILE"
else
  echo "COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT_NAME" >> "$ENV_FILE"
fi

# Update or add WORKSPACE_FOLDER_NAME (original case for file paths)
if grep -q "^WORKSPACE_FOLDER_NAME=" "$ENV_FILE"; then
  sed -i "s|^WORKSPACE_FOLDER_NAME=.*$|WORKSPACE_FOLDER_NAME=$WORKSPACE_FOLDER_NAME|" "$ENV_FILE"
else
  echo "WORKSPACE_FOLDER_NAME=$WORKSPACE_FOLDER_NAME" >> "$ENV_FILE"
fi

echo "Configured PROJECT_ROOT=$PROJECT_ROOT, ACTIVE_PROJECT=$ACTIVE_PROJECT (lowercase for Docker), WORKSPACE_NAME=$WORKSPACE_NAME, WORKSPACE_FOLDER_NAME=$WORKSPACE_FOLDER_NAME (original case for paths), and COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT_NAME in $ENV_FILE"
