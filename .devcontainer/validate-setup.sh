#!/bin/bash
# Validate EC2 setup for devcontainer development
# Run this to check if your instance is ready for devcontainers

echo "🔍 Validating EC2 setup for devcontainer development..."
echo ""

FAILED=0

# Check Node.js availability
echo "📦 Checking Node.js..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "✅ Node.js found: $NODE_VERSION"
    
    # Check if it's globally available (not just in NVM)
    if [ -f "/usr/bin/node" ] || [ -f "/usr/local/bin/node" ]; then
        echo "✅ Node.js available globally"
    else
        echo "❌ Node.js not available globally (devcontainer CLI won't work)"
        echo "   Run: sudo ln -sf ~/.nvm/versions/node/*/bin/node /usr/bin/node"
        FAILED=1
    fi
else
    echo "❌ Node.js not found"
    echo "   Install with: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash && nvm install 16"
    FAILED=1
fi

echo ""

# Check Docker buildx version
echo "🐳 Checking Docker buildx..."
if command -v docker &> /dev/null; then
    BUILDX_VERSION=$(docker buildx version 2>/dev/null | grep -o '[0-9]*\.[0-9]*\.[0-9]*' | head -1)
    if [ -n "$BUILDX_VERSION" ]; then
        echo "✅ Docker buildx found: $BUILDX_VERSION"
        
        # Check if version is >= 0.17
        if [ "$(printf '%s\n' "0.17.0" "$BUILDX_VERSION" | sort -V | head -n1)" = "$BUILDX_VERSION" ]; then
            echo "❌ Buildx version too old (need 0.17+), current: $BUILDX_VERSION"
            echo "   Update with setup script: ./.devcontainer/setup-ec2-host.sh"
            FAILED=1
        else
            echo "✅ Buildx version is compatible"
        fi
    else
        echo "❌ Docker buildx not found"
        FAILED=1
    fi
else
    echo "❌ Docker not found"
    FAILED=1
fi

echo ""

# Check Docker Compose
echo "🐳 Checking Docker Compose..."
if command -v docker-compose &> /dev/null; then
    COMPOSE_VERSION=$(docker-compose --version)
    echo "✅ Docker Compose found: $COMPOSE_VERSION"
else
    echo "⚠️  Standalone docker-compose not found (docker compose plugin should work)"
fi

echo ""

# Check script permissions
echo "📄 Checking script permissions..."
if [ -f ".devcontainer/set-project-root.sh" ]; then
    if [ -x ".devcontainer/set-project-root.sh" ]; then
        echo "✅ set-project-root.sh is executable"
    else
        echo "❌ set-project-root.sh is not executable"
        echo "   Run: chmod +x .devcontainer/set-project-root.sh"
        FAILED=1
    fi
else
    echo "❌ set-project-root.sh not found"
    FAILED=1
fi

echo ""

# Test script execution
echo "🧪 Testing initialization script..."
if [ -x ".devcontainer/set-project-root.sh" ]; then
    if ./.devcontainer/set-project-root.sh >/dev/null 2>&1; then
        echo "✅ Initialization script runs successfully"
    else
        echo "❌ Initialization script failed"
        echo "   Test manually: ./.devcontainer/set-project-root.sh"
        FAILED=1
    fi
else
    echo "⏭️  Skipping script test (not executable)"
fi

echo ""

# Summary
if [ $FAILED -eq 0 ]; then
    echo "🎉 All checks passed! Your EC2 instance is ready for devcontainer development."
    echo ""
    echo "Next steps:"
    echo "1. Open this project in Cursor"
    echo "2. Press Ctrl+Shift+P"
    echo "3. Select 'Dev Containers: Rebuild and Reopen in Container'"
    echo ""
else
    echo "❌ Setup validation failed. Please address the issues above."
    echo ""
    echo "Quick fix: run the automated setup script:"
    echo "  ./.devcontainer/setup-ec2-host.sh"
    echo ""
    exit 1
fi
