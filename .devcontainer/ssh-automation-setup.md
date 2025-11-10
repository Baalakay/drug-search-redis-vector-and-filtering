# SSH Key Automation for New EC2 Instances

## 🎯 **Goal**
Automatically configure SSH access when new EC2 instances are created so developers can connect immediately without manual setup.

## 📋 **Options (Choose One)**

### **Option 1: SSM Parameter Store (RECOMMENDED)**

**Most secure and flexible approach**

1. **Store your public key in SSM Parameter Store:**
```bash
# Get your public key
cat ~/.ssh/id_rsa.pub

# Store it in SSM Parameter Store
aws ssm put-parameter \
    --name "/devcontainer/ssh-keys/blake-macbook-pro" \
    --value "$(cat ~/.ssh/id_rsa.pub)" \
    --type "String" \
    --description "Blake's MacBook Pro SSH public key for devcontainers"
```

2. **Update launch template user data:**
   - Edit `/workspaces/DAW/.devcontainer/launch-template-userdata-with-ssh.sh`
   - Uncomment and modify the "OPTION 1" section:
   ```bash
   PARAMETER_NAME="/devcontainer/ssh-keys/blake-macbook-pro"
   if aws ssm get-parameter --name "$PARAMETER_NAME" --query 'Parameter.Value' --output text 2>/dev/null; then
       echo "📥 Retrieving SSH key from SSM Parameter Store..."
       SSH_PUBLIC_KEY=$(aws ssm get-parameter --name "$PARAMETER_NAME" --query 'Parameter.Value' --output text)
       echo "$SSH_PUBLIC_KEY" >> /home/ec2-user/.ssh/authorized_keys
       echo "✅ SSH key added from SSM Parameter Store"
   else
       echo "⚠️ SSH key not found in SSM Parameter Store: $PARAMETER_NAME"
   fi
   ```

3. **Ensure IAM permissions:**
   Your EC2 instance role needs: `ssm:GetParameter` on the parameter

**✅ Pros:** Secure, centralized, easy to rotate keys
**❌ Cons:** Requires IAM setup

---

### **Option 2: Direct Key in Launch Template**

**Simplest but less secure approach**

1. **Get your public key:**
```bash
cat ~/.ssh/id_rsa.pub
```

2. **Update launch template user data:**
   - Edit `/workspaces/DAW/.devcontainer/launch-template-userdata-with-ssh.sh` 
   - Uncomment and modify the "OPTION 2" section:
   ```bash
   echo "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ[YOUR_ACTUAL_KEY_HERE] blake@Blakes-MacBook-Pro.local" >> /home/ec2-user/.ssh/authorized_keys
   ```

**✅ Pros:** Simple, no dependencies
**❌ Cons:** Key visible in launch template, harder to rotate

---

### **Option 3: GitHub Public Keys**

**Good for teams using GitHub**

1. **Upload your SSH key to GitHub** (if not already done)

2. **Update launch template user data:**
   - Edit `/workspaces/DAW/.devcontainer/launch-template-userdata-with-ssh.sh`
   - Uncomment and modify the "OPTION 3" section:
   ```bash
   GITHUB_USERNAME="yourusername"
   if curl -s "https://github.com/$GITHUB_USERNAME.keys"; then
       echo "📥 Retrieving SSH keys from GitHub..."
       curl -s "https://github.com/$GITHUB_USERNAME.keys" >> /home/ec2-user/.ssh/authorized_keys
       echo "✅ SSH keys added from GitHub"
   fi
   ```

**✅ Pros:** Easy for teams, uses existing GitHub keys
**❌ Cons:** Requires public GitHub profile, all your GitHub keys get access

---

### **Option 4: Private S3 Bucket**

**Good for organizations with existing S3 infrastructure**

1. **Upload your public key to S3:**
```bash
aws s3 cp ~/.ssh/id_rsa.pub s3://your-private-bucket/ssh-keys/blake-public-key.pub
```

2. **Update launch template user data:**
   - Uncomment and modify the "OPTION 4" section in the script

**✅ Pros:** Flexible, can store multiple keys
**❌ Cons:** Requires S3 bucket setup and IAM permissions

---

## 🚀 **Implementation Steps**

### **Step 1: Choose your approach** (Option 1 recommended)

### **Step 2: Update your EC2 Launch Template**
1. Go to AWS Console → EC2 → Launch Templates
2. Select your devcontainer launch template  
3. Create new version
4. In **User Data**, paste the contents of `launch-template-userdata-with-ssh.sh`
5. Uncomment and configure your chosen SSH option
6. Set as default version

### **Step 3: Test with new instance**
1. Launch new EC2 instance from updated template
2. Wait 2-3 minutes for user data to complete
3. Test SSH: `ssh ec2-devcontainer`
4. Should connect automatically! 🎉

### **Step 4: Update your team's documentation**
Document which SSH key approach you're using for team members.

---

## 🔧 **Troubleshooting**

### **Check if user data completed:**
```bash
# SSH via Session Manager first
aws ssm start-session --target i-INSTANCEID

# Check logs
sudo tail -50 /var/log/user-data.log
```

### **Verify SSH key was added:**
```bash
cat /home/ec2-user/.ssh/authorized_keys
```

### **Test SSH key manually:**
```bash
ssh-keygen -l -f /home/ec2-user/.ssh/authorized_keys
```

---

## 🔄 **Key Rotation**

- **Option 1 (SSM):** Update parameter, terminate/recreate instances
- **Option 2 (Direct):** Update launch template, recreate instances  
- **Option 3 (GitHub):** Update GitHub keys, recreate instances
- **Option 4 (S3):** Update S3 object, recreate instances

---

## 🛡️ **Security Best Practices**

1. **Use Option 1 (SSM Parameter Store)** for production
2. **Rotate SSH keys regularly**
3. **Use separate keys per environment** (dev/staging/prod)
4. **Monitor SSH access** via CloudTrail
5. **Use least-privilege IAM policies**

---

## 🎉 **Result**

After setup:
- ✅ **New EC2 instances** launch fully configured
- ✅ **SSH access** works immediately  
- ✅ **Devcontainers** work without manual setup
- ✅ **Team members** can connect instantly
- ✅ **No manual intervention** required
