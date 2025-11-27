#!/bin/bash
# Quick setup script for SSH key automation using SSM Parameter Store (RECOMMENDED)

set -e

echo "🔐 Setting up SSH key automation for EC2 devcontainer instances"
echo ""

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &>/dev/null; then
    echo "❌ AWS CLI not configured. Please run 'aws configure' first."
    exit 1
fi

# Check if SSH key exists
SSH_KEY_PATH="$HOME/.ssh/id_rsa.pub"
if [ ! -f "$SSH_KEY_PATH" ]; then
    echo "❌ SSH public key not found at $SSH_KEY_PATH"
    echo "Please generate one first: ssh-keygen -t rsa -f ~/.ssh/id_rsa -N ''"
    exit 1
fi

echo "✅ Found SSH public key at $SSH_KEY_PATH"

# Show the key for verification
echo ""
echo "Your SSH public key:"
echo "$(cat $SSH_KEY_PATH)"
echo ""

# Ask for confirmation
read -p "Store this key in SSM Parameter Store for automatic EC2 setup? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 0
fi

# Generate parameter name based on hostname
HOSTNAME=$(hostname | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g')
PARAMETER_NAME="/devcontainer/ssh-keys/$HOSTNAME"

echo ""
echo "📥 Storing SSH key in SSM Parameter Store..."
echo "Parameter name: $PARAMETER_NAME"

# Store the SSH key in SSM Parameter Store
aws ssm put-parameter \
    --name "$PARAMETER_NAME" \
    --value "$(cat $SSH_KEY_PATH)" \
    --type "String" \
    --description "SSH public key for devcontainer access from $HOSTNAME" \
    --overwrite

echo "✅ SSH key stored successfully!"
echo ""
echo "🚀 Next steps:"
echo "1. Update your EC2 Launch Template with the user data script"
echo "2. Uncomment the SSM Parameter Store section"
echo "3. Set PARAMETER_NAME=\"$PARAMETER_NAME\""
echo "4. Ensure your EC2 instance role has ssm:GetParameter permission"
echo ""
echo "📁 Files to check:"
echo "- launch-template-userdata-with-ssh.sh (main script)"
echo "- ssh-automation-setup.md (full documentation)"
echo ""
echo "🎉 After setup, new EC2 instances will have automatic SSH access!"
