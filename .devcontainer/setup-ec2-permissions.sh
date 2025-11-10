#!/bin/bash
# Script to add necessary permissions to the EC2 instance role
# This allows the EC2 instance to manage launch templates and other AWS resources

set -e

echo "🔧 Setting up EC2 instance permissions for AWS resource management..."
echo ""

# Get current role information
ROLE_NAME="ecsInstanceRole"
ACCOUNT_ID="750389970429"

echo "📋 Current role: $ROLE_NAME"
echo "📋 Account ID: $ACCOUNT_ID"
echo ""

# Check if policy already exists
POLICY_NAME="DevcontainerManagementPolicy"
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"

echo "🔍 Checking if policy exists..."
if aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
    echo "✅ Policy already exists: $POLICY_NAME"
    
    # Update existing policy
    echo "📝 Updating policy with latest permissions..."
    aws iam create-policy-version \
        --policy-arn "$POLICY_ARN" \
        --policy-document file:///workspaces/DAW/.devcontainer/ec2-management-policy.json \
        --set-as-default
    echo "✅ Policy updated successfully"
else
    echo "📝 Creating new policy: $POLICY_NAME"
    aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document file:///workspaces/DAW/.devcontainer/ec2-management-policy.json \
        --description "Allows EC2 instances to manage launch templates and devcontainer resources"
    echo "✅ Policy created successfully"
fi

# Check if policy is attached to role
echo ""
echo "🔍 Checking if policy is attached to role..."
if aws iam list-attached-role-policies --role-name "$ROLE_NAME" --query "AttachedPolicies[?PolicyArn=='$POLICY_ARN']" --output text | grep -q "$POLICY_ARN"; then
    echo "✅ Policy already attached to role"
else
    echo "🔗 Attaching policy to role..."
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn "$POLICY_ARN"
    echo "✅ Policy attached successfully"
fi

echo ""
echo "🎉 EC2 permissions setup complete!"
echo ""
echo "📋 Added permissions for:"
echo "- ✅ Launch template management (describe, create versions, modify)"
echo "- ✅ EC2 instance information (describe instances, images, etc.)"  
echo "- ✅ SSM Parameter Store (get/put parameters for SSH keys)"
echo "- ✅ IAM role management (limited to this role and devcontainer policies)"
echo ""
echo "🚀 This EC2 instance can now:"
echo "- Update launch templates directly"
echo "- Manage SSH keys in SSM Parameter Store" 
echo "- View and modify its own IAM permissions"
echo "- Automate AWS resource management for devcontainers"
echo ""
echo "⚠️ Note: It may take 1-2 minutes for new permissions to propagate"
