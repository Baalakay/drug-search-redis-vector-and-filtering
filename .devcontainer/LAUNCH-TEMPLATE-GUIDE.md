# Launch Template vs Project Setup Guide

## 🚨 **Avoiding Duplication Issues**

You're right to be concerned about duplication! Here's how to properly separate instance-level vs. project-level setup:

## 📋 **What Goes Where**

### 🏗️ **EC2 Launch Template (Instance Level)**
**File: `launch-template-userdata.sh`**

**Put in Launch Template User Data:**
- ✅ Docker installation 
- ✅ Docker Compose installation
- ✅ Node.js via NVM (instance-wide)
- ✅ AWS CLI installation
- ✅ Basic development tools
- ✅ System package updates
- ✅ User group permissions (`docker` group)

**Benefits:**
- ✅ Every new instance is immediately ready
- ✅ No waiting for setup on each project clone
- ✅ Consistent baseline across all instances

### 🎯 **Project Setup (Project Level)**
**Files: `setup-ec2-host-minimal.sh` or `setup-ec2-host.sh`**

**Keep in Project Repository:**
- ✅ Docker buildx version verification/updates
- ✅ Global Node.js symlink verification  
- ✅ Project-specific validations
- ✅ Shell environment verification
- ✅ Script permissions fixing

**Benefits:**
- ✅ Handles launch template failures gracefully
- ✅ Project-specific requirements
- ✅ Version-specific compatibility checks

## 🔄 **Two Setup Strategies**

### **Strategy 1: Launch Template + Minimal Project Setup** ⭐ **RECOMMENDED**

```bash
# 1. Add to your EC2 Launch Template User Data:
# (Copy contents of launch-template-userdata.sh)

# 2. In your project, run minimal setup:
./.devcontainer/setup-ec2-host-minimal.sh

# 3. Use devcontainer normally
```

### **Strategy 2: Full Project Setup (No Launch Template)**

```bash
# If no launch template, use full setup:
./.devcontainer/setup-ec2-host.sh
```

## ⚠️ **Potential Conflicts & Solutions**

| Issue | Cause | Solution |
|-------|-------|----------|
| **Node.js version conflicts** | Launch template installs different version | Project setup detects and uses existing or updates |
| **Docker buildx outdated** | Launch template has older buildx | Project setup always verifies and updates buildx |
| **Permission conflicts** | Different user contexts | Scripts check permissions and fix as needed |
| **Duplicate installations** | Both try to install same thing | Project setup checks if already installed first |

## 🛡️ **Conflict Prevention Design**

Our scripts prevent conflicts by:

1. **Detection First**: Always check if software exists before installing
2. **Version Verification**: Ensure minimum required versions
3. **Graceful Fallbacks**: Handle cases where launch template failed
4. **Non-Destructive Updates**: Only update what's actually needed
5. **Error Handling**: Continue on non-critical failures

## 📝 **Launch Template Implementation**

### **Step 1: Add to Launch Template**
```bash
# In AWS Console > Launch Templates > User Data:
# Copy the entire contents of launch-template-userdata.sh
```

### **Step 2: Update Project Documentation**
```bash
# Update your project README to use minimal setup:
git clone [repo]
cd [repo]
./.devcontainer/setup-ec2-host-minimal.sh  # Instead of full setup
```

### **Step 3: Test Both Scenarios**
```bash
# Test with launch template:
./.devcontainer/setup-ec2-host-minimal.sh

# Test without launch template:
./.devcontainer/setup-ec2-host.sh
```

## 🧪 **Validation**

Always validate with:
```bash
./.devcontainer/validate-setup.sh
```

This works regardless of whether you used launch template or project setup.

## 📊 **Recommended File Usage**

| Scenario | Use This File | Notes |
|----------|---------------|-------|
| **With Launch Template** | `setup-ec2-host-minimal.sh` | Fast, assumes basics installed |
| **Without Launch Template** | `setup-ec2-host.sh` | Complete installation |
| **Validation** | `validate-setup.sh` | Works in both scenarios |
| **Launch Template User Data** | `launch-template-userdata.sh` | Copy to AWS Console |

## 🎯 **Benefits of Proper Separation**

- ⚡ **Faster instance startup** - basics pre-installed
- 🔒 **Reliable project setup** - handles edge cases  
- 🔄 **No duplication conflicts** - smart detection
- 📈 **Scalable** - works across multiple projects
- 🛡️ **Fault tolerant** - graceful fallbacks

The key is that launch template handles the **instance baseline**, while project setup handles **project-specific requirements and validation**.
