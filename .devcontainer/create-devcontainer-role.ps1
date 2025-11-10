# PowerShell script to create a dedicated IAM role for devcontainer EC2 instances
# This keeps permissions separate from other EC2 instances

$ErrorActionPreference = "Stop"

Write-Host "🔧 Creating dedicated devcontainer IAM role and permissions..." -ForegroundColor Green
Write-Host ""

$RoleName = "DevcontainerInstanceRole"
$PolicyName = "DevcontainerInstancePolicy" 
$InstanceProfileName = "DevcontainerInstanceProfile"
$AccountId = "750389970429"

# Create the IAM role
Write-Host "📝 Creating IAM role: $RoleName" -ForegroundColor Yellow
try {
    aws iam get-role --role-name $RoleName | Out-Null
    Write-Host "✅ Role already exists: $RoleName" -ForegroundColor Green
} catch {
    aws iam create-role `
        --role-name $RoleName `
        --assume-role-policy-document file://devcontainer-iam-role-policy.json `
        --description "IAM role for devcontainer EC2 instances with launch template management"
    Write-Host "✅ Created role: $RoleName" -ForegroundColor Green
}

# Create the policy
Write-Host ""
Write-Host "📝 Creating IAM policy: $PolicyName" -ForegroundColor Yellow
$PolicyArn = "arn:aws:iam::${AccountId}:policy/${PolicyName}"

try {
    aws iam get-policy --policy-arn $PolicyArn | Out-Null
    Write-Host "✅ Policy already exists: $PolicyName" -ForegroundColor Green
    
    # Update existing policy
    Write-Host "📝 Updating policy with latest permissions..." -ForegroundColor Yellow
    aws iam create-policy-version `
        --policy-arn $PolicyArn `
        --policy-document file://devcontainer-permissions-policy.json `
        --set-as-default
    Write-Host "✅ Policy updated successfully" -ForegroundColor Green
} catch {
    aws iam create-policy `
        --policy-name $PolicyName `
        --policy-document file://devcontainer-permissions-policy.json `
        --description "Permissions for devcontainer EC2 instances"
    Write-Host "✅ Created policy: $PolicyName" -ForegroundColor Green
}

# Attach policy to role
Write-Host ""
Write-Host "🔗 Attaching policy to role..." -ForegroundColor Yellow
aws iam attach-role-policy `
    --role-name $RoleName `
    --policy-arn $PolicyArn
Write-Host "✅ Policy attached to role" -ForegroundColor Green

# Create instance profile
Write-Host ""
Write-Host "📝 Creating instance profile: $InstanceProfileName" -ForegroundColor Yellow
try {
    aws iam get-instance-profile --instance-profile-name $InstanceProfileName | Out-Null
    Write-Host "✅ Instance profile already exists: $InstanceProfileName" -ForegroundColor Green
} catch {
    aws iam create-instance-profile --instance-profile-name $InstanceProfileName
    Write-Host "✅ Created instance profile: $InstanceProfileName" -ForegroundColor Green
}

# Add role to instance profile
Write-Host ""
Write-Host "🔗 Adding role to instance profile..." -ForegroundColor Yellow
$ExistingRole = aws iam get-instance-profile --instance-profile-name $InstanceProfileName --query "InstanceProfile.Roles[?RoleName=='$RoleName']" --output text
if ($ExistingRole -match $RoleName) {
    Write-Host "✅ Role already in instance profile" -ForegroundColor Green
} else {
    aws iam add-role-to-instance-profile `
        --instance-profile-name $InstanceProfileName `
        --role-name $RoleName
    Write-Host "✅ Added role to instance profile" -ForegroundColor Green
}

Write-Host ""
Write-Host "🎉 Dedicated devcontainer IAM role created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Created resources:" -ForegroundColor Cyan
Write-Host "- ✅ IAM Role: $RoleName" -ForegroundColor Green
Write-Host "- ✅ IAM Policy: $PolicyName" -ForegroundColor Green
Write-Host "- ✅ Instance Profile: $InstanceProfileName" -ForegroundColor Green
Write-Host ""
Write-Host "🔒 Security benefits:" -ForegroundColor Cyan
Write-Host "- ✅ Separate role from other EC2 instances" -ForegroundColor Green
Write-Host "- ✅ Limited to devcontainer-specific permissions" -ForegroundColor Green
Write-Host "- ✅ No impact on existing EC2 instances" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 Next step: Update launch template to use this role" -ForegroundColor Yellow
Write-Host "   Instance Profile ARN: arn:aws:iam::${AccountId}:instance-profile/${InstanceProfileName}" -ForegroundColor White
