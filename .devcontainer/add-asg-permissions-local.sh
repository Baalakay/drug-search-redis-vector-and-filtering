#!/bin/bash
# Script to add Auto Scaling Group permissions to DevcontainerInstanceRole
# Run from local machine with AWS admin credentials

set -e

echo "🔧 Adding Auto Scaling Group permissions to DevcontainerInstanceRole..."
echo ""

POLICY_ARN="arn:aws:iam::750389970429:policy/DevcontainerInstancePolicy"

# Check if policy files exist locally
if [ ! -f "devcontainer-permissions-policy-updated.json" ]; then
    echo "❌ Missing: devcontainer-permissions-policy-updated.json"
    echo "Please copy it with: scp ec2-devcontainer:/workspaces/DAW/.devcontainer/devcontainer-permissions-policy-updated.json ."
    exit 1
fi

echo "📋 Updating policy: $POLICY_ARN"
echo ""

# Create new policy version with ASG permissions
echo "📝 Adding Auto Scaling Group permissions..."
aws iam create-policy-version \
    --policy-arn "$POLICY_ARN" \
    --policy-document file://devcontainer-permissions-policy-updated.json \
    --set-as-default

echo "✅ Policy updated successfully"
echo ""
echo "🎉 Added permissions for:"
echo "- ✅ Auto Scaling Groups (describe, update)"
echo "- ✅ Launch Configurations (describe)" 
echo "- ✅ Scaling Activities (describe)"
echo ""
echo "⏳ Permissions will propagate in 1-2 minutes"
echo "🚀 After that, the EC2 instance can check and manage ASGs directly!"
