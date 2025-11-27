# 🎉 Complete EC2 Devcontainer Automation

## 🚀 **What This Does**

Automatically sets up **fully ready EC2 devcontainer instances** with:
- ✅ **Host dependencies** (Node.js, Docker buildx, etc.)
- ✅ **SSH key access** (connect immediately without manual setup)
- ✅ **AWS credentials sharing** (via bind mount)
- ✅ **Zero manual steps** required

## 📋 **Files Overview**

| File | Purpose |
|------|---------|
| `launch-template-userdata-with-ssh.sh` | **Complete automation** - host setup + SSH keys |
| `setup-ssh-automation.sh` | **Quick setup** for SSH key automation |
| `ssh-automation-setup.md` | **Full documentation** for SSH options |
| `launch-template-userdata.sh` | Host setup only (manual SSH required) |

## 🚀 **Quick Start (Recommended)**

### **Step 1: Set up SSH automation** (one time)
```bash
# Run the quick setup script
./.devcontainer/setup-ssh-automation.sh
```

This stores your SSH public key in AWS SSM Parameter Store.

### **Step 2: Update your Launch Template**
1. Go to **AWS Console → EC2 → Launch Templates**
2. Select your devcontainer launch template
3. **Create new version**
4. In **User Data**, paste the contents of `launch-template-userdata-with-ssh.sh`
5. **Uncomment the SSM Parameter Store section** (lines ~47-54)
6. **Set as default version**

### **Step 3: Launch & Connect!**
```bash
# Launch new EC2 instance from template
# Wait 2-3 minutes for setup to complete

# SSH works immediately!
ssh ec2-devcontainer

# Clone and develop
git clone your-repo-url
cd your-repo

# Open in Cursor - devcontainer works perfectly!
```

## 🔧 **SSH Configuration (Mac)**

Your `~/.ssh/config` should have:
```ssh
Host ec2-devcontainer
    HostName i-YOUR-INSTANCE-ID
    User ec2-user
    ProxyCommand sh -c "aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
    StrictHostKeyChecking no
```

## 🔧 **SSH Configuration (Windows)**

Your `D:\Users\username\.ssh\config` should have:
```ssh
Host devcontainer-aws-pure
    HostName i-YOUR-INSTANCE-ID
    User ec2-user
    ProxyCommand powershell -Command "$env:PATH += ';C:\\Program Files\\Amazon\\SessionManagerPlugin\\bin'; aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
    StrictHostKeyChecking no
```

## 🛡️ **Security & IAM**

### **Required IAM Permissions**

Your **EC2 instance role** needs:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter"
            ],
            "Resource": "arn:aws:ssm:*:*:parameter/devcontainer/ssh-keys/*"
        }
    ]
}
```

Your **user/role** needs standard Session Manager permissions.

## 📊 **What Gets Installed**

The automation installs:

### **Host Dependencies**
- ✅ Docker & Docker Compose
- ✅ Node.js v16 (global access for devcontainer CLI)
- ✅ Docker buildx v0.18+ (for compose builds)
- ✅ AWS CLI
- ✅ Development tools

### **SSH Setup**  
- ✅ Your SSH public key in `authorized_keys`
- ✅ Proper `.ssh` directory permissions
- ✅ Ready for immediate SSH access

### **Directory Structure**
- ✅ `/home/ec2-user/.aws` (for credential bind mount)
- ✅ `/home/ec2-user/.ssh` (with your keys)
- ✅ All devcontainer requirements

## 🔄 **Alternative SSH Methods**

See `ssh-automation-setup.md` for other options:
- **GitHub public keys** (team-friendly)
- **Direct key in template** (simple but less secure)
- **S3 bucket** (enterprise)

## 🐛 **Troubleshooting**

### **SSH not working?**
```bash
# Check if user data completed
aws ssm start-session --target i-INSTANCEID
sudo tail -50 /var/log/user-data.log

# Verify SSH key was added
cat /home/ec2-user/.ssh/authorized_keys
```

### **Devcontainer build fails?**
```bash
# Verify Node.js is global
node --version
which node  # Should show /usr/bin/node

# Verify Docker buildx
docker buildx version  # Should be v0.17+
```

### **Session Manager issues?**
```bash
# Test basic Session Manager
aws ssm start-session --target i-INSTANCEID

# Check AWS credentials
aws sts get-caller-identity
```

## 🎯 **Success Criteria**

After following this setup:

- ✅ **Launch new EC2 instance** → Fully configured automatically
- ✅ **SSH connection** → `ssh ec2-devcontainer` works immediately  
- ✅ **Devcontainer rebuild** → Works without any setup
- ✅ **AWS credentials** → Available in devcontainer via bind mount
- ✅ **Zero manual steps** → Everything just works!

## 🔄 **Key Rotation**

To update SSH keys:
1. Update SSM Parameter Store: `aws ssm put-parameter --name "/devcontainer/ssh-keys/your-key" --value "$(cat ~/.ssh/id_rsa.pub)" --overwrite`
2. Terminate and recreate instances (they'll get the new key automatically)

## 🎉 **Result**

**Perfect devcontainer workflow:**
```bash
# 1. Launch EC2 instance (automated setup)
# 2. SSH immediately 
ssh ec2-devcontainer

# 3. Clone and develop
git clone your-repo && cd your-repo

# 4. Open in Cursor - everything works!
```

**No manual setup. No configuration. Just code!** 🚀
