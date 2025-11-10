#!/bin/bash
# Alternative file transfer method using Session Manager when SSH isn't working
# Run this script on your Mac to transfer AWS credentials

echo "🔄 Alternative AWS Credentials Transfer via Session Manager"
echo ""

# Check if AWS CLI works
if ! aws sts get-caller-identity >/dev/null 2>&1; then
    echo "❌ AWS CLI not configured. Run 'aws configure' first."
    exit 1
fi

echo "✅ AWS CLI working"

# Check Session Manager plugin
if ! command -v session-manager-plugin >/dev/null 2>&1; then
    echo "❌ Session Manager plugin not found. Install with:"
    echo "brew install --cask session-manager-plugin"
    exit 1
fi

echo "✅ Session Manager plugin found"

INSTANCE_ID="i-02566fac470923c7c"

# Test Session Manager connection
echo ""
echo "🧪 Testing Session Manager connection..."
timeout 5 aws ssm start-session --target $INSTANCE_ID --document-name AWS-StartSessionManagerSession >/dev/null 2>&1
if [ $? -eq 124 ]; then
    echo "✅ Session Manager connection works (timed out after 5s as expected)"
else
    echo "❌ Session Manager connection failed"
    exit 1
fi

echo ""
echo "📁 Preparing AWS credentials for transfer..."

# Create temporary transfer directory
TEMP_DIR=$(mktemp -d)
cp -r ~/.aws "$TEMP_DIR/"

# Create base64 encoded archive
cd "$TEMP_DIR"
tar czf aws-credentials.tar.gz .aws/
BASE64_CREDS=$(base64 < aws-credentials.tar.gz)

# Clean up temp directory
cd - > /dev/null
rm -rf "$TEMP_DIR"

echo "✅ AWS credentials prepared"

echo ""
echo "🚀 Transferring credentials..."
echo "This will open a Session Manager session where you can paste the encoded credentials."
echo ""
echo "Instructions:"
echo "1. Session Manager will open"
echo "2. Paste the following commands one by one:"
echo ""
echo "# Create transfer directory"
echo "mkdir -p /tmp/aws-transfer"
echo ""
echo "# Create the base64 file (paste this entire block as one command):"
echo "cat > /tmp/aws-transfer/creds.b64 << 'EOF'"
echo "$BASE64_CREDS"
echo "EOF"
echo ""
echo "# Decode and extract"
echo "cd /tmp/aws-transfer"
echo "base64 -d < creds.b64 > aws-creds.tar.gz"
echo "tar xzf aws-creds.tar.gz"
echo ""
echo "# Copy to ec2-user"
echo "sudo mkdir -p /home/ec2-user/.aws"
echo "sudo cp -r .aws/* /home/ec2-user/.aws/"
echo "sudo chown -R ec2-user:ec2-user /home/ec2-user/.aws"
echo "sudo chmod 600 /home/ec2-user/.aws/credentials"
echo "sudo chmod 644 /home/ec2-user/.aws/config"
echo ""
echo "# Test"
echo "sudo -u ec2-user aws sts get-caller-identity"
echo ""
echo "# Cleanup"
echo "rm -rf /tmp/aws-transfer"
echo "exit"
echo ""

read -p "Ready to open Session Manager? (y/N): " confirm
if [[ $confirm =~ ^[Yy]$ ]]; then
    echo ""
    echo "🔗 Opening Session Manager session..."
    aws ssm start-session --target $INSTANCE_ID
else
    echo "❌ Transfer cancelled"
fi
