#!/bin/bash
# Script to create a dedicated IAM role for devcontainer EC2 instances
# This keeps permissions separate from other EC2 instances

set -e

echo "🔧 Creating dedicated devcontainer IAM role and permissions..."
echo ""

ROLE_NAME="DevcontainerInstanceRole" 
POLICY_NAME="DevcontainerInstancePolicy"
INSTANCE_PROFILE_NAME="DevcontainerInstanceProfile"
ACCOUNT_ID="750389970429"

# Create the IAM role
echo "📝 Creating IAM role: $ROLE_NAME"
if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
    echo "✅ Role already exists: $ROLE_NAME"
else
    aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document file:///workspaces/DAW/.devcontainer/devcontainer-iam-role-policy.json \
        --description "IAM role for devcontainer EC2 instances with launch template management"
    echo "✅ Created role: $ROLE_NAME"
fi

# Create the policy
echo ""
echo "📝 Creating IAM policy: $POLICY_NAME"
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"

if aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
    echo "✅ Policy already exists: $POLICY_NAME"
    
    # Update existing policy
    echo "📝 Updating policy with latest permissions..."
    aws iam create-policy-version \
        --policy-arn "$POLICY_ARN" \
        --policy-document file:///workspaces/DAW/.devcontainer/devcontainer-permissions-policy.json \
        --set-as-default
    echo "✅ Policy updated successfully"
else
    aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document file:///workspaces/DAW/.devcontainer/devcontainer-permissions-policy.json \
        --description "Permissions for devcontainer EC2 instances"
    echo "✅ Created policy: $POLICY_NAME"
fi

# Attach policy to role
echo ""
echo "🔗 Attaching policy to role..."
aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn "$POLICY_ARN"
echo "✅ Policy attached to role"

# Create instance profile
echo ""
echo "📝 Creating instance profile: $INSTANCE_PROFILE_NAME"
if aws iam get-instance-profile --instance-profile-name "$INSTANCE_PROFILE_NAME" >/dev/null 2>&1; then
    echo "✅ Instance profile already exists: $INSTANCE_PROFILE_NAME"
else
    aws iam create-instance-profile \
        --instance-profile-name "$INSTANCE_PROFILE_NAME"
    echo "✅ Created instance profile: $INSTANCE_PROFILE_NAME"
fi

# Add role to instance profile
echo ""
echo "🔗 Adding role to instance profile..."
if aws iam get-instance-profile --instance-profile-name "$INSTANCE_PROFILE_NAME" --query 'InstanceProfile.Roles[?RoleName==`'$ROLE_NAME'`]' --output text | grep -q "$ROLE_NAME"; then
    echo "✅ Role already in instance profile"
else
    aws iam add-role-to-instance-profile \
        --instance-profile-name "$INSTANCE_PROFILE_NAME" \
        --role-name "$ROLE_NAME"
    echo "✅ Added role to instance profile"
fi

echo ""
echo "🎉 Dedicated devcontainer IAM role created successfully!"
echo ""
echo "📋 Created resources:"
echo "- ✅ IAM Role: $ROLE_NAME"
echo "- ✅ IAM Policy: $POLICY_NAME" 
echo "- ✅ Instance Profile: $INSTANCE_PROFILE_NAME"
echo ""
echo "🔒 Security benefits:"
echo "- ✅ Separate role from other EC2 instances"
echo "- ✅ Limited to devcontainer-specific permissions"
echo "- ✅ No impact on existing EC2 instances"
echo ""
echo "🚀 Next step: Update launch template to use this role"
echo "   Instance Profile ARN: arn:aws:iam::${ACCOUNT_ID}:instance-profile/${INSTANCE_PROFILE_NAME}"
