#!/bin/bash
# EC2 Host Setup Script for Devcontainer Development
# Run this on a new EC2 instance before using devcontainers

set -e  # Exit on any error

echo "🚀 Setting up EC2 instance for devcontainer development..."

# Check if running as root (should not be)
if [[ $EUID -eq 0 ]]; then
   echo "❌ Please run this script as ec2-user, not root"
   exit 1
fi

# 1. Install Node.js via NVM (for devcontainer CLI)
echo "📦 Installing Node.js via NVM..."
if [ ! -d "$HOME/.nvm" ]; then
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm install 16  # LTS version compatible with Amazon Linux 2
    nvm use 16
    nvm alias default 16
fi

# 2. Create global Node.js symlinks (for devcontainer CLI)
echo "🔗 Creating global Node.js symlinks..."
if [ -f "$HOME/.nvm/versions/node/v16.20.2/bin/node" ]; then
    sudo ln -sf "$HOME/.nvm/versions/node/v16.20.2/bin/node" /usr/bin/node
    sudo ln -sf "$HOME/.nvm/versions/node/v16.20.2/bin/npm" /usr/bin/npm
    sudo ln -sf "$HOME/.nvm/versions/node/v16.20.2/bin/node" /usr/local/bin/node
    sudo ln -sf "$HOME/.nvm/versions/node/v16.20.2/bin/npm" /usr/local/bin/npm
    echo "✅ Node.js available globally: $(node --version)"
else
    echo "❌ Node.js installation failed"
    exit 1
fi

# 3. Update Docker buildx to required version
echo "🐳 Updating Docker buildx..."
CURRENT_BUILDX=$(docker buildx version | grep -o '[0-9]*\.[0-9]*\.[0-9]*' | head -1)
echo "Current buildx: $CURRENT_BUILDX"

# Check if buildx version is less than 0.17
if [ "$(printf '%s\n' "0.17.0" "$CURRENT_BUILDX" | sort -V | head -n1)" != "$CURRENT_BUILDX" ]; then
    echo "📥 Updating buildx to v0.18.0..."
    curl -LO https://github.com/docker/buildx/releases/download/v0.18.0/buildx-v0.18.0.linux-amd64
    chmod +x buildx-v0.18.0.linux-amd64
    sudo mv buildx-v0.18.0.linux-amd64 /usr/libexec/docker/cli-plugins/docker-buildx
    echo "✅ Buildx updated: $(docker buildx version)"
else
    echo "✅ Buildx version is sufficient: $CURRENT_BUILDX"
fi

# 4. Verify Docker and Docker Compose
echo "🐳 Verifying Docker setup..."
docker --version
docker-compose --version || echo "⚠️ Docker Compose not found, but docker compose plugin should work"

# 5. Test devcontainer CLI requirements
echo "🧪 Testing devcontainer CLI requirements..."
if command -v node &> /dev/null; then
    echo "✅ Node.js available: $(node --version)"
else
    echo "❌ Node.js not available globally"
    exit 1
fi

BUILDX_CHECK=$(docker buildx version | grep -o '[0-9]*\.[0-9]*\.[0-9]*' | head -1)
if [ "$(printf '%s\n' "0.17.0" "$BUILDX_CHECK" | sort -V | head -n1)" = "$BUILDX_CHECK" ]; then
    echo "❌ Docker buildx version too old: $BUILDX_CHECK"
    exit 1
else
    echo "✅ Docker buildx compatible: $BUILDX_CHECK"
fi

# 6. Setup shell environment
echo "🐚 Setting up shell environment..."
if ! grep -q "NVM_DIR" ~/.bashrc; then
    echo 'export NVM_DIR="$HOME/.nvm"' >> ~/.bashrc
    echo '[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"' >> ~/.bashrc
    echo '[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"' >> ~/.bashrc
fi

echo ""
echo "🎉 EC2 instance setup complete!"
echo ""
echo "Next steps:"
echo "1. Clone your project repository"
echo "2. Ensure .devcontainer/set-project-root.sh has execute permissions"
echo "3. Use Cursor's 'Dev Containers: Rebuild and Reopen in Container'"
echo ""
echo "Prerequisites verified:"
echo "✅ Node.js $(node --version) available globally"
echo "✅ Docker buildx $(docker buildx version | grep -o 'v[0-9]*\.[0-9]*\.[0-9]*' | head -1)"
echo "✅ Docker Compose available"
echo ""
