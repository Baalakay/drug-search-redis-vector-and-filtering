#!/bin/bash
# Quick setup script to receive AWS credentials from Mac
# Run this on EC2 after copying credentials via ssm-user

echo "🔐 Setting up AWS credentials for ec2-user from Mac transfer..."

# Create .aws directory for ec2-user if it doesn't exist
sudo mkdir -p /home/ec2-user/.aws

# Check if ssm-user has credentials to copy
if [ -f /home/ssm-user/.aws/credentials ] || [ -f /home/ssm-user/.aws/config ]; then
    echo "📋 Found AWS credentials from Mac transfer"
    
    # Copy credentials from ssm-user to ec2-user
    if [ -f /home/ssm-user/.aws/credentials ]; then
        sudo cp /home/ssm-user/.aws/credentials /home/ec2-user/.aws/
        echo "✅ Copied credentials file"
    fi
    
    if [ -f /home/ssm-user/.aws/config ]; then
        sudo cp /home/ssm-user/.aws/config /home/ec2-user/.aws/
        echo "✅ Copied config file"
    fi
    
    # Copy entire directory if it exists
    if [ -d /home/ssm-user/.aws ]; then
        sudo cp -r /home/ssm-user/.aws/* /home/ec2-user/.aws/ 2>/dev/null
    fi
    
    # Set proper ownership
    sudo chown -R ec2-user:ec2-user /home/ec2-user/.aws
    sudo chmod 600 /home/ec2-user/.aws/credentials 2>/dev/null
    sudo chmod 644 /home/ec2-user/.aws/config 2>/dev/null
    
    echo "✅ Set proper permissions"
    
    # Clean up ssm-user copy (optional)
    read -p "Remove AWS credentials from ssm-user home? (y/N): " cleanup
    if [[ $cleanup =~ ^[Yy]$ ]]; then
        sudo rm -rf /home/ssm-user/.aws
        echo "🧹 Cleaned up ssm-user credentials"
    fi
    
else
    echo "❌ No AWS credentials found in /home/ssm-user/.aws/"
    echo ""
    echo "📋 Instructions:"
    echo "1. From your Mac, run:"
    echo "   scp -r ~/.aws/ ec2-devcontainer:~/"
    echo ""
    echo "2. Then run this script again"
    exit 1
fi

echo ""
echo "🧪 Testing AWS credentials..."
if sudo -u ec2-user aws sts get-caller-identity >/dev/null 2>&1; then
    echo "✅ AWS credentials working for ec2-user!"
    echo ""
    echo "Identity:"
    sudo -u ec2-user aws sts get-caller-identity
    echo ""
    echo "🎉 Setup complete! Your devcontainer will now have AWS access."
else
    echo "❌ AWS credentials test failed"
    echo "Check the credentials and try again"
fi
