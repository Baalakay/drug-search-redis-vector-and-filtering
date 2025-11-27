#!/bin/bash
# Add Windows SSH key to existing EC2 instance via SSM Parameter Store

echo "🔑 Adding Windows SSH key to existing EC2 instance..."

# Parameter name for Windows key
WINDOWS_PARAMETER="/devcontainer/ssh-keys/blake-windows"

# Check if parameter exists
if aws ssm get-parameter --name "$WINDOWS_PARAMETER" --query 'Parameter.Value' --output text 2>/dev/null; then
    echo "📥 Retrieving Windows SSH key from SSM Parameter Store..."
    
    # Get the key
    WINDOWS_SSH_KEY=$(aws ssm get-parameter --name "$WINDOWS_PARAMETER" --query 'Parameter.Value' --output text)
    
    # Add to authorized_keys if not already present
    if ! grep -q "$WINDOWS_SSH_KEY" /home/ec2-user/.ssh/authorized_keys 2>/dev/null; then
        echo "$WINDOWS_SSH_KEY" >> /home/ec2-user/.ssh/authorized_keys
        echo "✅ Windows SSH key added to authorized_keys"
    else
        echo "✅ Windows SSH key already present in authorized_keys"
    fi
    
    # Fix permissions
    chmod 600 /home/ec2-user/.ssh/authorized_keys
    chown ec2-user:ec2-user /home/ec2-user/.ssh/authorized_keys
    
    echo "🎉 Windows SSH key setup complete!"
    echo "Test from Windows: ssh devcontainer"
    
else
    echo "❌ Windows SSH key not found in SSM Parameter Store: $WINDOWS_PARAMETER"
    echo "Please run this on Windows first:"
    echo "aws ssm put-parameter --name \"$WINDOWS_PARAMETER\" --value \"\$(Get-Content \$env:USERPROFILE\\.ssh\\id_rsa.pub)\" --type \"String\" --overwrite"
    exit 1
fi
