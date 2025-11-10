# Mac SSH + Session Manager Setup for EC2

This guide helps you set up SSH access from your Mac to EC2 instances via AWS Session Manager, enabling direct SCP file transfers.

## 📋 Prerequisites

1. **AWS CLI configured** on your Mac with appropriate permissions
2. **EC2 instance** with Session Manager access (IAM role with `AmazonSSMManagedInstanceCore`)

## 🔧 Step 1: Install Session Manager Plugin on Mac

### Option A: Using Homebrew (Recommended)
```bash
brew install --cask session-manager-plugin
```

### Option B: Manual Installation
```bash
# Download the plugin
curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/mac_amd64/sessionmanager-bundle.zip" -o "sessionmanager-bundle.zip"

# Extract and install
unzip sessionmanager-bundle.zip
sudo ./sessionmanager-bundle/install -i /usr/local/sessionmanagerplugin -b /usr/local/bin/session-manager-plugin

# Verify installation
session-manager-plugin
```

## 🔧 Step 2: Configure SSH on Mac

Create or update your SSH config file:

```bash
# Edit SSH config
nano ~/.ssh/config
```

Add this configuration:

```ssh
# AWS Session Manager SSH Configuration
Host i-* mi-*
    ProxyCommand sh -c "aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
    User ec2-user
    IdentitiesOnly yes
    # Optional: Specify your key file
    # IdentityFile ~/.ssh/your-key.pem

# Specific host for your current instance
Host daw-devcontainer
    HostName i-02566fac470923c7c
    ProxyCommand sh -c "aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
    User ec2-user
    IdentitiesOnly yes
```

## 🔧 Step 3: Test SSH Connection

```bash
# Test connection using instance ID
ssh i-02566fac470923c7c

# Or using the alias
ssh daw-devcontainer
```

## 📁 Step 4: Use SCP for File Transfers

### Copy AWS Credentials
```bash
# Copy credentials file
scp ~/.aws/credentials daw-devcontainer:~/.aws/

# Copy config file  
scp ~/.aws/config daw-devcontainer:~/.aws/

# Copy entire .aws directory
scp -r ~/.aws/ daw-devcontainer:~/
```

### Copy Other Files
```bash
# Copy single file
scp /path/to/local/file daw-devcontainer:/path/to/remote/

# Copy directory
scp -r /path/to/local/directory/ daw-devcontainer:/path/to/remote/

# Copy from EC2 to Mac
scp daw-devcontainer:/path/to/remote/file /path/to/local/
```

## 🛠️ Advanced Configuration

### Multiple AWS Profiles
If you use multiple AWS profiles, specify the profile:

```bash
# In SSH config, add profile specification
Host daw-devcontainer-prod
    HostName i-1234567890abcdef0
    ProxyCommand sh -c "AWS_PROFILE=production aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
    User ec2-user
```

### Persistent Connections
Add to SSH config for faster repeated connections:

```ssh
Host i-* mi-*
    ProxyCommand sh -c "aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
    User ec2-user
    IdentitiesOnly yes
    # Connection multiplexing for speed
    ControlMaster auto
    ControlPath ~/.ssh/sockets/ssh-%r@%h-%p
    ControlPersist 10m
```

Create the sockets directory:
```bash
mkdir -p ~/.ssh/sockets
```

## 🔍 Troubleshooting

### Check Session Manager Access
```bash
# Verify instance is managed by Session Manager
aws ssm describe-instance-information --filters "Key=InstanceIds,Values=i-02566fac470923c7c"

# Test session manager directly
aws ssm start-session --target i-02566fac470923c7c
```

### Common Issues

1. **"No such file or directory"** → Install Session Manager plugin
2. **"Permission denied"** → Check AWS credentials and IAM permissions
3. **"Connection timeout"** → Verify instance has Session Manager agent and proper IAM role

### Required IAM Permissions (for your AWS user/role)
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ssm:StartSession"
            ],
            "Resource": [
                "arn:aws:ec2:*:*:instance/*",
                "arn:aws:ssm:*:*:document/AWS-StartSSHSession"
            ]
        }
    ]
}
```

## 🚀 Quick Start Commands

```bash
# 1. Install plugin
brew install --cask session-manager-plugin

# 2. Add SSH config
cat >> ~/.ssh/config << 'EOF'
Host daw-devcontainer
    HostName i-02566fac470923c7c
    ProxyCommand sh -c "aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
    User ec2-user
    IdentitiesOnly yes
EOF

# 3. Test connection
ssh daw-devcontainer

# 4. Copy AWS credentials
scp -r ~/.aws/ daw-devcontainer:~/
```

## 📝 Notes

- **No SSH keys required** - Session Manager handles authentication via AWS credentials
- **Works through NAT/private subnets** - No need for public IPs or bastion hosts  
- **Encrypted traffic** - All traffic goes through AWS Session Manager service
- **Audit trail** - All sessions are logged in CloudTrail
