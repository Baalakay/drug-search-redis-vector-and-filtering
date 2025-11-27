#!/bin/bash
# Script to update launch template with dedicated devcontainer IAM role and complete automation

set -e

echo "🚀 Updating launch template with dedicated role and complete automation..."
echo ""

INSTANCE_PROFILE_NAME="DevcontainerInstanceProfile"
ACCOUNT_ID="750389970429"
INSTANCE_PROFILE_ARN="arn:aws:iam::${ACCOUNT_ID}:instance-profile/${INSTANCE_PROFILE_NAME}"

# Find launch templates
echo "🔍 Finding launch templates..."
LAUNCH_TEMPLATES=$(aws ec2 describe-launch-templates --query 'LaunchTemplates[?contains(LaunchTemplateName, `devcontainer`) || contains(LaunchTemplateName, `DAW`) || contains(LaunchTemplateName, `dev`)].{Name:LaunchTemplateName,Id:LaunchTemplateId}' --output json)

if [ "$LAUNCH_TEMPLATES" = "[]" ]; then
    echo "❌ No devcontainer-related launch templates found."
    echo "Please provide your launch template name:"
    read -p "Launch Template Name: " TEMPLATE_NAME
    TEMPLATE_ID=$(aws ec2 describe-launch-templates --launch-template-names "$TEMPLATE_NAME" --query 'LaunchTemplates[0].LaunchTemplateId' --output text)
else
    echo "📋 Found launch templates:"
    echo "$LAUNCH_TEMPLATES" | jq -r '.[] | "\(.Name) (\(.Id))"'
    echo ""
    read -p "Enter the Launch Template Name to update: " TEMPLATE_NAME
    TEMPLATE_ID=$(echo "$LAUNCH_TEMPLATES" | jq -r ".[] | select(.Name==\"$TEMPLATE_NAME\") | .Id")
fi

if [ -z "$TEMPLATE_ID" ] || [ "$TEMPLATE_ID" = "null" ]; then
    echo "❌ Launch template not found: $TEMPLATE_NAME"
    exit 1
fi

echo "✅ Found launch template: $TEMPLATE_NAME ($TEMPLATE_ID)"
echo ""

# Get current launch template version to preserve settings
echo "📋 Getting current launch template configuration..."
CURRENT_DATA=$(aws ec2 describe-launch-template-versions \
    --launch-template-id "$TEMPLATE_ID" \
    --versions '$Default' \
    --query 'LaunchTemplateVersions[0].LaunchTemplateData' \
    --output json)

# Get the user data script
USER_DATA_FILE="/workspaces/DAW/.devcontainer/launch-template-userdata-with-ssh.sh"
if [ ! -f "$USER_DATA_FILE" ]; then
    echo "❌ User data script not found: $USER_DATA_FILE"
    exit 1
fi

# Base64 encode the user data
USER_DATA_B64=$(base64 -w 0 "$USER_DATA_FILE")

echo "📝 Creating new launch template version with dedicated role..."

# Merge current settings with new IAM instance profile and user data
NEW_TEMPLATE_DATA=$(echo "$CURRENT_DATA" | jq --arg profile_arn "$INSTANCE_PROFILE_ARN" --arg user_data "$USER_DATA_B64" '
    .IamInstanceProfile = {
        "Arn": $profile_arn
    } |
    .UserData = $user_data
')

# Create new version
NEW_VERSION=$(aws ec2 create-launch-template-version \
    --launch-template-id "$TEMPLATE_ID" \
    --launch-template-data "$NEW_TEMPLATE_DATA" \
    --query 'LaunchTemplateVersion.VersionNumber' \
    --output text)

echo "✅ Created launch template version: $NEW_VERSION"

# Set as default version
aws ec2 modify-launch-template \
    --launch-template-id "$TEMPLATE_ID" \
    --default-version "$NEW_VERSION"

echo "✅ Set version $NEW_VERSION as default"
echo ""
echo "🎉 Launch Template Updated Successfully!"
echo ""
echo "📋 Summary:"
echo "- Template: $TEMPLATE_NAME ($TEMPLATE_ID)"  
echo "- New Version: $NEW_VERSION (now default)"
echo "- IAM Role: DevcontainerInstanceRole (dedicated)"
echo "- Automation: Complete host setup + SSH keys"
echo ""
echo "🔒 Security improvements:"
echo "- ✅ Dedicated IAM role (not shared with other instances)"
echo "- ✅ Limited permissions scope"
echo "- ✅ No impact on existing EC2 instances"
echo ""
echo "🚀 Next new EC2 instances will:"
echo "- Use dedicated devcontainer IAM role"
echo "- Install all dependencies automatically" 
echo "- Pull SSH keys from SSM Parameter Store"
echo "- Be ready for SSH + devcontainers in 2-3 minutes"
echo "- Have permissions to self-manage AWS resources"
echo ""
echo "Test by launching a new instance from this template!"
