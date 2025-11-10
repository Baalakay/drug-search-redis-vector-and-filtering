#!/bin/bash
# Helper script to securely copy AWS credentials to EC2
# Run this to set up temporary access until your dotfiles scripts are working

echo "🔐 AWS Credentials Setup for EC2 Instance"
echo ""

# Create the .aws directory if it doesn't exist
mkdir -p /home/ec2-user/.aws
cd /home/ec2-user/.aws

echo "Choose your method to copy credentials:"
echo ""
echo "1. Paste credentials directly (secure terminal session)"
echo "2. SCP from another machine"  
echo "3. Create temporary credentials manually"
echo "4. Use AWS CLI configure"
echo ""

read -p "Select method (1-4): " METHOD

case $METHOD in
    1)
        echo ""
        echo "📋 Method 1: Direct paste"
        echo "This will create credentials and config files"
        echo ""
        
        echo "Creating ~/.aws/credentials file..."
        echo "Paste your credentials file content (Ctrl+D when done):"
        cat > /home/ec2-user/.aws/credentials
        
        echo ""
        echo "Creating ~/.aws/config file..."
        echo "Paste your config file content (Ctrl+D when done):"
        cat > /home/ec2-user/.aws/config
        
        echo "✅ Files created"
        ;;
        
    2)
        echo ""
        echo "📤 Method 2: SCP from another machine"
        echo ""
        echo "From your Mac (or any machine with your credentials), run:"
        echo ""
        echo "scp ~/.aws/credentials ec2-user@$(curl -s http://169.254.169.254/latest/meta-data/public-hostname):~/.aws/"
        echo "scp ~/.aws/config ec2-user@$(curl -s http://169.254.169.254/latest/meta-data/public-hostname):~/.aws/"
        echo ""
        echo "Or using IP:"
        echo "scp ~/.aws/credentials ec2-user@$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):~/.aws/"
        echo "scp ~/.aws/config ec2-user@$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):~/.aws/"
        echo ""
        read -p "Press Enter after you've copied the files..."
        ;;
        
    3)
        echo ""
        echo "🔑 Method 3: Manual temporary credentials"
        echo ""
        read -p "AWS Access Key ID: " ACCESS_KEY
        read -s -p "AWS Secret Access Key: " SECRET_KEY
        echo ""
        read -p "Default region (e.g., us-east-1): " REGION
        read -p "Default output format (json): " OUTPUT
        OUTPUT=${OUTPUT:-json}
        
        cat > /home/ec2-user/.aws/credentials << EOF
[default]
aws_access_key_id = $ACCESS_KEY
aws_secret_access_key = $SECRET_KEY
EOF

        cat > /home/ec2-user/.aws/config << EOF
[default]
region = $REGION
output = $OUTPUT
EOF
        
        echo "✅ Basic credentials created"
        ;;
        
    4)
        echo ""
        echo "⚙️  Method 4: AWS CLI configure"
        aws configure
        ;;
        
    *)
        echo "❌ Invalid selection"
        exit 1
        ;;
esac

# Set proper permissions
chmod 600 /home/ec2-user/.aws/credentials
chmod 644 /home/ec2-user/.aws/config
chown -R ec2-user:ec2-user /home/ec2-user/.aws

echo ""
echo "🧪 Testing AWS credentials..."
if aws sts get-caller-identity >/dev/null 2>&1; then
    echo "✅ AWS credentials working!"
    echo ""
    echo "Identity:"
    aws sts get-caller-identity
else
    echo "❌ AWS credentials test failed"
    echo "Check your credentials and try again"
fi

echo ""
echo "📋 Next steps:"
echo "1. Your credentials are now in /home/ec2-user/.aws/"
echo "2. When you rebuild the devcontainer, they'll be available at /home/vscode/.aws/"
echo "3. Your dotfiles AWS scripts will be able to read/update these files"
echo "4. Run your AWS setup script from inside the devcontainer to configure profiles"
echo ""
