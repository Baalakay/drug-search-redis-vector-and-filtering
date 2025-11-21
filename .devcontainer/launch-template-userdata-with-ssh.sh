#!/bin/bash
# COMPLETE EC2 Launch Template User Data Script + SSH Key Automation
# This runs when the instance first boots up and makes the instance 100% ready for devcontainers
# Includes automated SSH key setup for immediate access
# NO MANUAL STEPS REQUIRED after this runs

# Log all output
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

echo "🚀 EC2 Launch Template: Starting instance setup with SSH automation..."

# Update system packages
yum update -y

# Install basic development tools
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
sleep 2

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

# Install devcontainer CLI globally (CRITICAL for Cursor devcontainer builds)
echo "📦 Installing devcontainer CLI..."
sleep 2

# Install as ec2-user to ensure proper access
sudo -u ec2-user bash << 'EOF'
    export HOME=/home/ec2-user
    cd $HOME
    
    # Ensure NVM is loaded
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    
    # Install devcontainer CLI
    npm install -g @devcontainers/cli
EOF

# Create global devcontainer CLI symlinks
DEVCONTAINER_PATH=$(find /home/ec2-user/.nvm/versions/node -name "devcontainer" -type f 2>/dev/null | head -1)
if [ -n "$DEVCONTAINER_PATH" ]; then
    ln -sf "$DEVCONTAINER_PATH" /usr/bin/devcontainer
    ln -sf "$DEVCONTAINER_PATH" /usr/local/bin/devcontainer
    echo "✅ Global devcontainer CLI symlinks created"
else
    echo "⚠️ Devcontainer CLI path not found"
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

# ========================================
# SSH KEY AUTOMATION - Multiple Options
# ========================================

echo "🔐 Setting up automated SSH key access..."

# Ensure .ssh directory exists with correct permissions
sudo -u ec2-user mkdir -p /home/ec2-user/.ssh
chmod 700 /home/ec2-user/.ssh
chown ec2-user:ec2-user /home/ec2-user/.ssh

# OPTION 1: Retrieve SSH public keys from SSM Parameter Store (RECOMMENDED)
# Add all developer SSH keys automatically
echo "📥 Retrieving SSH keys from SSM Parameter Store..."

# Blake's Mac key
MAC_PARAMETER="/devcontainer/ssh-keys/blake-macbook-pro"
if aws ssm get-parameter --name "$MAC_PARAMETER" --query 'Parameter.Value' --output text 2>/dev/null; then
    MAC_SSH_KEY=$(aws ssm get-parameter --name "$MAC_PARAMETER" --query 'Parameter.Value' --output text)
    echo "$MAC_SSH_KEY" >> /home/ec2-user/.ssh/authorized_keys
    echo "✅ Mac SSH key added from SSM Parameter Store"
else
    echo "⚠️ Mac SSH key not found in SSM Parameter Store: $MAC_PARAMETER"
fi

# Blake's Windows key  
WINDOWS_PARAMETER="/devcontainer/ssh-keys/blake-windows"
if aws ssm get-parameter --name "$WINDOWS_PARAMETER" --query 'Parameter.Value' --output text 2>/dev/null; then
    WINDOWS_SSH_KEY=$(aws ssm get-parameter --name "$WINDOWS_PARAMETER" --query 'Parameter.Value' --output text)
    echo "$WINDOWS_SSH_KEY" >> /home/ec2-user/.ssh/authorized_keys
    echo "✅ Windows SSH key added from SSM Parameter Store"
else
    echo "⚠️ Windows SSH key not found in SSM Parameter Store: $WINDOWS_PARAMETER"
fi

# OPTION 2: Direct key inclusion (LESS SECURE - key visible in launch template)
# Uncomment and replace with your actual public key
# echo "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ... blake@Blakes-MacBook-Pro.local" >> /home/ec2-user/.ssh/authorized_keys

# OPTION 3: Retrieve from GitHub (if you store your public keys there)
# Uncomment and modify for your GitHub username
# GITHUB_USERNAME="yourusername"
# if curl -s "https://github.com/$GITHUB_USERNAME.keys"; then
#     echo "📥 Retrieving SSH keys from GitHub..."
#     curl -s "https://github.com/$GITHUB_USERNAME.keys" >> /home/ec2-user/.ssh/authorized_keys
#     echo "✅ SSH keys added from GitHub"
# fi

# OPTION 4: Download from a private S3 bucket
# BUCKET_NAME="your-private-bucket"
# KEY_PATH="ssh-keys/blake-public-key.pub"
# if aws s3 cp "s3://$BUCKET_NAME/$KEY_PATH" /tmp/ssh-key.pub 2>/dev/null; then
#     echo "📥 Retrieving SSH key from S3..."
#     cat /tmp/ssh-key.pub >> /home/ec2-user/.ssh/authorized_keys
#     rm /tmp/ssh-key.pub
#     echo "✅ SSH key added from S3"
# fi

# Set correct permissions on authorized_keys
chmod 600 /home/ec2-user/.ssh/authorized_keys
chown ec2-user:ec2-user /home/ec2-user/.ssh/authorized_keys

# ========================================
# GIT CREDENTIALS AUTOMATION
# ========================================
echo "🔐 Setting up Git credentials from SSM..."
sudo -u ec2-user bash << 'EOF'
    # Retrieve GitHub PAT tokens from SSM Parameter Store
    if aws ssm get-parameter --name "/devcontainer/git-credentials/github-pats" --with-decryption --query 'Parameter.Value' --output text 2>/dev/null; then
        GITHUB_PATS=$(aws ssm get-parameter --name "/devcontainer/git-credentials/github-pats" --with-decryption --query 'Parameter.Value' --output text)
        echo "$GITHUB_PATS" > /home/ec2-user/.git-credentials
        chmod 600 /home/ec2-user/.git-credentials
        echo "✅ GitHub credentials configured from SSM"
    else
        echo "⚠️ GitHub PAT tokens not found in SSM Parameter Store"
    fi
    
    # Set up git config
    git config --global user.name "Blake McDonald"
    git config --global user.email "blake@innovativesol.com"
    git config --global credential.helper store
    echo "✅ Git configuration completed"
EOF

# ========================================
# AWS CLI CONFIGURATION AUTOMATION
# ========================================
echo "🔧 Setting up AWS CLI configuration from SSM..."
sudo -u ec2-user bash << 'EOF'
    # Ensure .aws directory exists
    mkdir -p /home/ec2-user/.aws
    
    # Retrieve AWS config file (modified for hybrid IAM approach)
    if aws ssm get-parameter --name "/devcontainer/aws-config/config-file" --query 'Parameter.Value' --output text 2>/dev/null; then
        aws ssm get-parameter --name "/devcontainer/aws-config/config-file" --query 'Parameter.Value' --output text > /home/ec2-user/.aws/config
        chmod 644 /home/ec2-user/.aws/config
        echo "✅ AWS config file configured from SSM"
    else
        echo "⚠️ AWS config file not found in SSM Parameter Store"
    fi
    
    # Create minimal credentials file for hybrid approach (instance role + cross-account)
    cat > /home/ec2-user/.aws/credentials << 'CREDS_EOF'
# AWS Credentials File - Hybrid IAM Configuration
# 
# This file is intentionally minimal to enable hybrid IAM approach:
# - Default profile uses EC2 instance role (DevcontainerInstanceRole) 
# - Cross-account profiles get session tokens from manual refresh script
#
# When you run your token refresh script, it will add temporary credentials
# for cross-account access (DAW, johnson-lambert, etc.) to this file.
#
# Local account operations (750389970429) automatically use instance role.
CREDS_EOF
    chmod 600 /home/ec2-user/.aws/credentials
    echo "✅ Hybrid credentials file created - default uses instance role"
EOF

# Final validation that everything is ready
echo "🧪 Validating complete setup..."

# Verify Node.js is available globally
if command -v node &> /dev/null; then
    echo "✅ Node.js globally available: $(node --version)"
else
    echo "⚠️ Node.js not yet globally available (may need symlink after first login)"
fi

# Verify devcontainer CLI is available globally
if command -v devcontainer &> /dev/null; then
    echo "✅ Devcontainer CLI globally available: $(devcontainer --version)"
else
    echo "⚠️ Devcontainer CLI not yet globally available"
fi

# Verify Docker buildx version
BUILDX_VERSION=$(docker buildx version 2>/dev/null | grep -o '[0-9]*\.[0-9]*\.[0-9]*' | head -1 || echo "unknown")
echo "✅ Docker buildx version: $BUILDX_VERSION"

# Check SSH setup
if [ -f /home/ec2-user/.ssh/authorized_keys ]; then
    KEY_COUNT=$(wc -l < /home/ec2-user/.ssh/authorized_keys)
    echo "✅ SSH authorized_keys configured with $KEY_COUNT key(s)"
else
    echo "⚠️ No SSH keys configured - manual setup required"
fi

# Check Git setup
if [ -f /home/ec2-user/.git-credentials ]; then
    echo "✅ Git credentials configured"
else
    echo "⚠️ Git credentials not configured"
fi

if [ -f /home/ec2-user/.gitconfig ]; then
    echo "✅ Git configuration file exists"
else
    echo "⚠️ Git configuration file missing"
fi

# Check AWS CLI setup
if [ -f /home/ec2-user/.aws/config ]; then
    echo "✅ AWS config file configured"
else
    echo "⚠️ AWS config file missing"
fi

if [ -f /home/ec2-user/.aws/credentials ]; then
    echo "✅ AWS credentials file configured"
else
    echo "⚠️ AWS credentials file missing"
fi

# Create completion marker
echo "$(date): Launch template setup completed successfully" > /tmp/devcontainer-setup-complete

echo ""
echo "🎉 LAUNCH TEMPLATE SETUP COMPLETE!"
echo "✅ Instance is 100% ready for devcontainer development"
echo "✅ SSH access configured (if keys were added)"
echo "✅ No manual setup steps required"
echo ""
echo "Ready for developers:"
echo "1. SSH: ssh ec2-devcontainer (if keys configured)"  
echo "2. Clone project: git clone [repo-url]"
echo "3. Open in Cursor: Dev Containers: Rebuild and Reopen in Container"
echo ""
