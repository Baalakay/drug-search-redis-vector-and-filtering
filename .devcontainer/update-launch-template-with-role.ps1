# PowerShell script to update launch template with dedicated devcontainer IAM role and complete automation

$ErrorActionPreference = "Stop"

Write-Host "🚀 Updating launch template with dedicated role and complete automation..." -ForegroundColor Green
Write-Host ""

$InstanceProfileName = "DevcontainerInstanceProfile"
$AccountId = "750389970429"
$InstanceProfileArn = "arn:aws:iam::${AccountId}:instance-profile/${InstanceProfileName}"

# Find launch templates
Write-Host "🔍 Finding launch templates..." -ForegroundColor Yellow
$LaunchTemplatesJson = aws ec2 describe-launch-templates --query 'LaunchTemplates[?contains(LaunchTemplateName, `devcontainer`) || contains(LaunchTemplateName, `DAW`) || contains(LaunchTemplateName, `dev`)].{Name:LaunchTemplateName,Id:LaunchTemplateId}' --output json | ConvertFrom-Json

if ($LaunchTemplatesJson.Count -eq 0) {
    Write-Host "❌ No devcontainer-related launch templates found." -ForegroundColor Red
    $TemplateName = Read-Host "Please provide your launch template name"
    $TemplateId = aws ec2 describe-launch-templates --launch-template-names $TemplateName --query 'LaunchTemplates[0].LaunchTemplateId' --output text
} else {
    Write-Host "📋 Found launch templates:" -ForegroundColor Cyan
    foreach ($template in $LaunchTemplatesJson) {
        Write-Host "- $($template.Name) ($($template.Id))" -ForegroundColor White
    }
    Write-Host ""
    $TemplateName = Read-Host "Enter the Launch Template Name to update"
    $TemplateId = ($LaunchTemplatesJson | Where-Object { $_.Name -eq $TemplateName }).Id
}

if (-not $TemplateId -or $TemplateId -eq "null") {
    Write-Host "❌ Launch template not found: $TemplateName" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Found launch template: $TemplateName ($TemplateId)" -ForegroundColor Green
Write-Host ""

# Get current launch template version to preserve settings
Write-Host "📋 Getting current launch template configuration..." -ForegroundColor Yellow
$CurrentDataJson = aws ec2 describe-launch-template-versions `
    --launch-template-id $TemplateId `
    --versions '$Default' `
    --query 'LaunchTemplateVersions[0].LaunchTemplateData' `
    --output json

# Get the user data script
$UserDataFile = "launch-template-userdata-with-ssh.sh"
if (-not (Test-Path $UserDataFile)) {
    Write-Host "❌ User data script not found: $UserDataFile" -ForegroundColor Red
    exit 1
}

# Base64 encode the user data (PowerShell way)
$UserDataContent = Get-Content $UserDataFile -Raw
$UserDataBytes = [System.Text.Encoding]::UTF8.GetBytes($UserDataContent)
$UserDataB64 = [System.Convert]::ToBase64String($UserDataBytes)

Write-Host "📝 Creating new launch template version with dedicated role..." -ForegroundColor Yellow

# Parse current data and add new settings
$CurrentData = $CurrentDataJson | ConvertFrom-Json
$CurrentData | Add-Member -Type NoteProperty -Name 'IamInstanceProfile' -Value @{
    'Arn' = $InstanceProfileArn
} -Force
$CurrentData | Add-Member -Type NoteProperty -Name 'UserData' -Value $UserDataB64 -Force

# Convert back to JSON for AWS CLI
$NewTemplateDataJson = $CurrentData | ConvertTo-Json -Depth 10 -Compress

# Create new version
Write-Host "Creating launch template version..." -ForegroundColor Yellow
$NewVersion = aws ec2 create-launch-template-version `
    --launch-template-id $TemplateId `
    --launch-template-data $NewTemplateDataJson `
    --query 'LaunchTemplateVersion.VersionNumber' `
    --output text

Write-Host "✅ Created launch template version: $NewVersion" -ForegroundColor Green

# Set as default version
aws ec2 modify-launch-template `
    --launch-template-id $TemplateId `
    --default-version $NewVersion

Write-Host "✅ Set version $NewVersion as default" -ForegroundColor Green
Write-Host ""
Write-Host "🎉 Launch Template Updated Successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Summary:" -ForegroundColor Cyan
Write-Host "- Template: $TemplateName ($TemplateId)" -ForegroundColor White
Write-Host "- New Version: $NewVersion (now default)" -ForegroundColor White
Write-Host "- IAM Role: DevcontainerInstanceRole (dedicated)" -ForegroundColor White
Write-Host "- Automation: Complete host setup + SSH keys" -ForegroundColor White
Write-Host ""
Write-Host "🔒 Security improvements:" -ForegroundColor Cyan
Write-Host "- ✅ Dedicated IAM role (not shared with other instances)" -ForegroundColor Green
Write-Host "- ✅ Limited permissions scope" -ForegroundColor Green
Write-Host "- ✅ No impact on existing EC2 instances" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 Next new EC2 instances will:" -ForegroundColor Yellow
Write-Host "- Use dedicated devcontainer IAM role" -ForegroundColor White
Write-Host "- Install all dependencies automatically" -ForegroundColor White
Write-Host "- Pull SSH keys from SSM Parameter Store" -ForegroundColor White
Write-Host "- Be ready for SSH + devcontainers in 2-3 minutes" -ForegroundColor White
Write-Host "- Have permissions to self-manage AWS resources" -ForegroundColor White
Write-Host ""
Write-Host "Test by launching a new instance from this template!" -ForegroundColor Yellow
