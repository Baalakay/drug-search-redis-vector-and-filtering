#!/bin/bash
# Run this script on your Mac to set up SSH config for Session Manager

echo "🔧 Setting up SSH configuration for AWS Session Manager on Mac..."

# Create .ssh directory if it doesn't exist
if [ ! -d "$HOME/.ssh" ]; then
    echo "📁 Creating ~/.ssh directory..."
    mkdir -p "$HOME/.ssh"
    chmod 700 "$HOME/.ssh"
fi

# Check if config file exists
if [ ! -f "$HOME/.ssh/config" ]; then
    echo "📄 Creating ~/.ssh/config file..."
    touch "$HOME/.ssh/config"
    chmod 600 "$HOME/.ssh/config"
fi

# Add the Session Manager configuration
echo ""
echo "📝 Adding Session Manager configuration..."

# Check if our config already exists
if grep -q "Host daw-devcontainer" "$HOME/.ssh/config"; then
    echo "⚠️  Configuration for 'daw-devcontainer' already exists in ~/.ssh/config"
    echo "Please check and update manually if needed."
else
    # Backup existing config
    if [ -s "$HOME/.ssh/config" ]; then
        cp "$HOME/.ssh/config" "$HOME/.ssh/config.backup.$(date +%Y%m%d_%H%M%S)"
        echo "📋 Backed up existing config to ~/.ssh/config.backup.*"
    fi
    
    # Add our configuration
    cat >> "$HOME/.ssh/config" << 'EOF'

# AWS Session Manager Configuration for DAW Devcontainer
Host daw-devcontainer
    HostName i-02566fac470923c7c
    ProxyCommand sh -c "aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
    User ec2-user
    IdentitiesOnly yes

# General AWS Session Manager configuration for any instance
Host i-* mi-*
    ProxyCommand sh -c "aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
    User ec2-user
    IdentitiesOnly yes
EOF

    echo "✅ SSH configuration added successfully!"
fi

echo ""
echo "🧪 Testing Session Manager plugin..."
if command -v session-manager-plugin >/dev/null 2>&1; then
    echo "✅ Session Manager plugin is installed"
else
    echo "❌ Session Manager plugin not found"
    echo ""
    echo "Install it with:"
    echo "  brew install --cask session-manager-plugin"
    echo ""
    echo "Or download manually from:"
    echo "  https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html"
fi

echo ""
echo "🧪 Testing AWS CLI..."
if aws sts get-caller-identity >/dev/null 2>&1; then
    echo "✅ AWS CLI is configured and working"
    echo "Current identity:"
    aws sts get-caller-identity
else
    echo "❌ AWS CLI not configured or not working"
    echo "Make sure you have AWS credentials configured:"
    echo "  aws configure"
fi

echo ""
echo "🚀 Setup complete! Next steps:"
echo ""
echo "1. Test SSH connection:"
echo "   ssh daw-devcontainer"
echo ""
echo "2. Copy AWS credentials:"
echo "   scp -r ~/.aws/ daw-devcontainer:~/"
echo ""
echo "3. Copy any other files:"
echo "   scp /path/to/file daw-devcontainer:/home/ec2-user/"
echo ""
