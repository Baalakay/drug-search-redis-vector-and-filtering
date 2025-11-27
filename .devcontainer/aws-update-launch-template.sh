#!/bin/bash
# Update Launch Template - run this with AWS admin credentials
# Option 1: Run from your local machine with AWS CLI
# Option 2: Configure AWS credentials on this instance and run here

echo "🚀 Automated Launch Template Updater"
echo ""

# Check for AWS CLI
AWS_CLI="aws"
if command -v /usr/local/bin/aws &> /dev/null; then
    AWS_CLI="/usr/local/bin/aws"
fi

# Test AWS access
echo "🔍 Testing AWS access..."
CALLER_ID=$($AWS_CLI sts get-caller-identity 2>/dev/null || echo "FAILED")
if [[ "$CALLER_ID" == "FAILED" ]]; then
    echo "❌ No AWS access found."
    echo ""
    echo "To run this script, you need AWS credentials with EC2 permissions."
    echo ""
    echo "Options:"
    echo "1. Run from your local machine: ./aws-update-launch-template.sh"
    echo "2. Configure AWS credentials here: aws configure"
    echo "3. Use IAM role with EC2 permissions"
    exit 1
fi

echo "✅ AWS Access confirmed"
echo "$CALLER_ID"
echo ""

# List available Launch Templates
echo "📋 Finding Launch Templates..."
TEMPLATES=$($AWS_CLI ec2 describe-launch-templates --query 'LaunchTemplates[*].[LaunchTemplateName,LaunchTemplateId]' --output text 2>/dev/null)

if [[ -z "$TEMPLATES" ]]; then
    echo "❌ No Launch Templates found or insufficient permissions"
    echo "Need ec2:DescribeLaunchTemplates permission"
    exit 1
fi

echo "Available Launch Templates:"
echo "$TEMPLATES" | nl -w2 -s'. '
echo ""

# Get template selection
echo "Select Launch Template (enter number):"
read -p "> " SELECTION

TEMPLATE_INFO=$(echo "$TEMPLATES" | sed -n "${SELECTION}p")
if [[ -z "$TEMPLATE_INFO" ]]; then
    echo "❌ Invalid selection"
    exit 1
fi

TEMPLATE_NAME=$(echo "$TEMPLATE_INFO" | awk '{print $1}')
TEMPLATE_ID=$(echo "$TEMPLATE_INFO" | awk '{print $2}')

echo "Selected: $TEMPLATE_NAME ($TEMPLATE_ID)"
echo ""

# Prepare user data
echo "📝 Preparing devcontainer user data..."
USER_DATA_FILE="/tmp/devcontainer-userdata-$(date +%s).sh"
cp "/workspaces/DAW/.devcontainer/launch-template-userdata.sh" "$USER_DATA_FILE"

# Encode for AWS
USER_DATA_ENCODED=$(base64 -w 0 "$USER_DATA_FILE")

echo "🚀 Creating new Launch Template version..."

# Create new version
NEW_VERSION=$($AWS_CLI ec2 create-launch-template-version \
    --launch-template-id "$TEMPLATE_ID" \
    --version-description "Devcontainer-ready setup - $(date '+%Y-%m-%d %H:%M')" \
    --launch-template-data "{\"UserData\":\"$USER_DATA_ENCODED\"}" \
    --query 'LaunchTemplateVersion.VersionNumber' \
    --output text)

if [[ -z "$NEW_VERSION" ]]; then
    echo "❌ Failed to create new version"
    exit 1
fi

echo "✅ Created version $NEW_VERSION"

# Ask about setting as default
read -p "Set as default version? (Y/n): " SET_DEFAULT
if [[ "$SET_DEFAULT" != "n" ]] && [[ "$SET_DEFAULT" != "N" ]]; then
    $AWS_CLI ec2 modify-launch-template \
        --launch-template-id "$TEMPLATE_ID" \
        --default-version "$NEW_VERSION" >/dev/null
    echo "✅ Set as default version"
fi

# Cleanup
rm -f "$USER_DATA_FILE"

echo ""
echo "🎉 Launch Template updated successfully!"
echo ""
echo "📋 What this means:"
echo "✅ New instances launched from '$TEMPLATE_NAME' will be devcontainer-ready"
echo "✅ No manual setup required - fully automated"
echo "✅ Node.js, Docker buildx, and all dependencies installed automatically"
echo ""
echo "🚀 Next steps:"
echo "1. Launch a new instance from this template"
echo "2. Wait 3-5 minutes for setup to complete"  
echo "3. SSH in and clone your project"
echo "4. Open in Cursor → Dev Containers: Rebuild and Reopen in Container"
echo ""
