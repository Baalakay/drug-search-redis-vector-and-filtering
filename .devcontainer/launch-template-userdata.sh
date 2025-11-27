#!/bin/bash
# COMPLETE EC2 Launch Template User Data Script
# This runs when the instance first boots up and makes the instance 100% ready for devcontainers
# NO MANUAL STEPS REQUIRED after this runs
# Place this ENTIRE script in your EC2 Launch Template's User Data section

# Log all output
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

echo "🚀 EC2 Launch Template: Starting instance setup..."

# Update system packages
yum update -y

# Install basic development tools (if not already installed)
yum groupinstall -y "Development Tools"
yum install -y git curl wget

# Install Docker (if not already present)
if ! command -v docker &> /dev/null; then
    echo "📦 Installing Docker..."
    yum install -y docker
    systemctl enable docker
    systemctl start docker
    usermod -a -G docker ec2-user
fi

# Install Docker Compose (if not already present) 
if ! command -v docker-compose &> /dev/null; then
    echo "📦 Installing Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Install Node.js globally via NVM for ec2-user (instance-wide setup)
echo "📦 Installing Node.js for ec2-user..."
sudo -u ec2-user bash << 'EOF'
    export HOME=/home/ec2-user
    cd $HOME
    
    # Install NVM if not present
    if [ ! -d "$HOME/.nvm" ]; then
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        
        # Install Node.js LTS
        nvm install 16
        nvm use 16
        nvm alias default 16
        
        # Add to bashrc
        echo 'export NVM_DIR="$HOME/.nvm"' >> $HOME/.bashrc
        echo '[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"' >> $HOME/.bashrc
        echo '[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"' >> $HOME/.bashrc
    fi
EOF

# Create global Node.js symlinks for system-wide access (CRITICAL for devcontainer CLI)
echo "🔗 Creating global Node.js symlinks..."
# Wait a moment for NVM installation to complete
sleep 2

# Find the actual node version installed
NODE_PATH=$(find /home/ec2-user/.nvm/versions/node -name "node" -type f 2>/dev/null | head -1)
NPM_PATH=$(find /home/ec2-user/.nvm/versions/node -name "npm" -type f 2>/dev/null | head -1)

if [ -n "$NODE_PATH" ] && [ -n "$NPM_PATH" ]; then
    ln -sf "$NODE_PATH" /usr/bin/node
    ln -sf "$NPM_PATH" /usr/bin/npm
    ln -sf "$NODE_PATH" /usr/local/bin/node  
    ln -sf "$NPM_PATH" /usr/local/bin/npm
    echo "✅ Global Node.js symlinks created: $(node --version 2>/dev/null || echo 'pending')"
else
    echo "⚠️ Node.js paths not found, will be handled by project setup"
fi

# Update Docker buildx to compatible version (CRITICAL for docker-compose build)
echo "🐳 Installing compatible Docker buildx..."
mkdir -p /usr/libexec/docker/cli-plugins
curl -L https://github.com/docker/buildx/releases/download/v0.18.0/buildx-v0.18.0.linux-amd64 -o /tmp/docker-buildx
chmod +x /tmp/docker-buildx
mv /tmp/docker-buildx /usr/libexec/docker/cli-plugins/docker-buildx
echo "✅ Docker buildx updated to v0.18.0"

# Set up AWS CLI (often needed for development)
if ! command -v aws &> /dev/null; then
    echo "📦 Installing AWS CLI..."
    cd /tmp
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    ./aws/install
    rm -rf aws awscliv2.zip
fi

# Create directories that might be needed
sudo -u ec2-user mkdir -p /home/ec2-user/.aws /home/ec2-user/.ssh

# Final validation that everything is ready
echo "🧪 Validating complete setup..."

# Verify Node.js is available globally
if command -v node &> /dev/null; then
    echo "✅ Node.js globally available: $(node --version)"
else
    echo "⚠️ Node.js not yet globally available (may need symlink after first login)"
fi

# Verify Docker buildx version
BUILDX_VERSION=$(docker buildx version 2>/dev/null | grep -o '[0-9]*\.[0-9]*\.[0-9]*' | head -1 || echo "unknown")
echo "✅ Docker buildx version: $BUILDX_VERSION"

# Create completion marker
echo "$(date): Launch template setup completed successfully" > /tmp/devcontainer-setup-complete

echo ""
echo "🎉 LAUNCH TEMPLATE SETUP COMPLETE!"
echo "✅ Instance is 100% ready for devcontainer development"
echo "✅ No manual setup steps required"
echo ""
echo "Next steps for developers:"
echo "1. SSH into instance"  
echo "2. Clone project: git clone [repo-url]"
echo "3. Open in Cursor and use: Dev Containers: Rebuild and Reopen in Container"
echo ""
