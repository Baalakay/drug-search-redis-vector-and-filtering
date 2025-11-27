#!/bin/bash
# Minimal EC2 Host Setup Script (for use with launch template)
# Run this if you have a launch template with basic setup already done
# This only handles project-specific configurations

set -e  # Exit on any error

echo "🎯 Project-specific EC2 setup (assumes launch template basics are installed)..."

# Check if running as root (should not be)
if [[ $EUID -eq 0 ]]; then
   echo "❌ Please run this script as ec2-user, not root"
   exit 1
fi

# 1. Verify Node.js is available and create symlinks if needed
echo "🔗 Ensuring Node.js is available globally..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "✅ Node.js found: $NODE_VERSION"
    
    # Ensure global symlinks exist (in case launch template missed this)
    if [ -f "$HOME/.nvm/versions/node/v16.20.2/bin/node" ]; then
        sudo ln -sf "$HOME/.nvm/versions/node/v16.20.2/bin/node" /usr/bin/node 2>/dev/null || true
        sudo ln -sf "$HOME/.nvm/versions/node/v16.20.2/bin/npm" /usr/bin/npm 2>/dev/null || true
    fi
else
    echo "❌ Node.js not found - launch template may have failed or you need the full setup script"
    echo "   Run ./.devcontainer/setup-ec2-host.sh for complete installation"
    exit 1
fi

# 2. Verify Docker buildx version
echo "🐳 Checking Docker buildx version..."
BUILDX_VERSION=$(docker buildx version 2>/dev/null | grep -o '[0-9]*\.[0-9]*\.[0-9]*' | head -1 || echo "0.0.0")
if [ "$(printf '%s\n' "0.17.0" "$BUILDX_VERSION" | sort -V | head -n1)" = "$BUILDX_VERSION" ]; then
    echo "⚠️  Buildx version too old: $BUILDX_VERSION - updating..."
    curl -LO https://github.com/docker/buildx/releases/download/v0.18.0/buildx-v0.18.0.linux-amd64
    chmod +x buildx-v0.18.0.linux-amd64
    sudo mv buildx-v0.18.0.linux-amd64 /usr/libexec/docker/cli-plugins/docker-buildx
    echo "✅ Buildx updated to: $(docker buildx version)"
else
    echo "✅ Buildx version compatible: $BUILDX_VERSION"
fi

# 3. Ensure shell environment is set up
echo "🐚 Verifying shell environment..."
if ! grep -q "NVM_DIR" ~/.bashrc 2>/dev/null; then
    echo "Adding NVM to bashrc..."
    echo 'export NVM_DIR="$HOME/.nvm"' >> ~/.bashrc
    echo '[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"' >> ~/.bashrc
    echo '[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"' >> ~/.bashrc
fi

# 4. Quick validation
echo "🧪 Running quick validation..."
if ! command -v node &> /dev/null || ! command -v docker &> /dev/null; then
    echo "❌ Basic requirements missing"
    exit 1
fi

echo ""
echo "🎉 Project setup complete!"
echo ""
echo "✅ Node.js $(node --version) available"
echo "✅ Docker buildx $(docker buildx version | grep -o '[0-9]*\.[0-9]*\.[0-9]*' | head -1)"
echo "✅ Ready for devcontainer development"
echo ""
echo "Next step: Use Cursor's 'Dev Containers: Rebuild and Reopen in Container'"
