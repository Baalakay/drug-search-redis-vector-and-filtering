# EC2 Devcontainer Setup Guide

## Prerequisites for New EC2 Instances

Before using devcontainers on a new EC2 instance, ensure these requirements are met:

### ✅ Required Software Versions
- **Node.js**: v16+ (required for devcontainer CLI)
- **Docker buildx**: v0.17+ (required for Docker Compose build)
- **Docker**: v20+ 
- **Docker Compose**: v2.0+

### 🚀 Quick Setup (Automated)

Run this on your new EC2 instance:

```bash
# 1. Clone your repository
git clone [your-repo-url]
cd [your-repo]

# 2. Run the automated setup script
./.devcontainer/setup-ec2-host.sh

# 3. Open in Cursor and rebuild devcontainer
```

### 🔧 Manual Setup (if automated script fails)

If you need to set up manually:

#### 1. Install Node.js globally
```bash
# Install NVM
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc

# Install Node.js v16 (Amazon Linux 2 compatible)
nvm install 16
nvm use 16
nvm alias default 16

# Create global symlinks for devcontainer CLI
sudo ln -sf ~/.nvm/versions/node/v16.20.2/bin/node /usr/bin/node
sudo ln -sf ~/.nvm/versions/node/v16.20.2/bin/npm /usr/bin/npm
```

#### 2. Update Docker buildx
```bash
# Check current version
docker buildx version

# If < v0.17.0, update:
curl -LO https://github.com/docker/buildx/releases/download/v0.18.0/buildx-v0.18.0.linux-amd64
chmod +x buildx-v0.18.0.linux-amd64
sudo mv buildx-v0.18.0.linux-amd64 /usr/libexec/docker/cli-plugins/docker-buildx
```

#### 3. Fix script permissions
```bash
chmod +x .devcontainer/set-project-root.sh
```

### 🎯 Verification

Before using devcontainers, verify:

```bash
# Node.js available globally
node --version          # Should show v16.x.x
which node              # Should show /usr/bin/node

# Docker buildx compatible
docker buildx version   # Should show v0.17.0+

# Docker Compose working
docker-compose --version

# Script executable
ls -la .devcontainer/set-project-root.sh  # Should show -rwxr-xr-x
```

### 🐛 Common Issues & Solutions

| Issue | Symptom | Solution |
|-------|---------|----------|
| Node.js not found | `get node path: Running command: node` error | Run: `sudo ln -sf ~/.nvm/versions/node/v16.20.2/bin/node /usr/bin/node` |
| Buildx too old | `compose build requires buildx 0.17 or later` | Update buildx using script above |
| Permission denied | `initializeCommand failed` | Run: `chmod +x .devcontainer/set-project-root.sh` |
| JSON parse errors | Feature processing errors | Use our fixed devcontainer.json configuration |

### 📋 New Instance Checklist

When setting up on a new EC2 instance:

- [ ] Run `setup-ec2-host.sh` script
- [ ] Verify Node.js: `node --version`
- [ ] Verify buildx: `docker buildx version`
- [ ] Check script permissions: `ls -la .devcontainer/set-project-root.sh`
- [ ] Test devcontainer rebuild in Cursor
- [ ] Confirm "Dev Container" appears in Cursor status bar

### 🔄 Troubleshooting

If devcontainer build fails:

1. **Check the error message** - look for specific failing component
2. **Verify prerequisites** - run verification commands above  
3. **Check logs** - look at Cursor's Output panel for detailed errors
4. **Test components individually**:
   ```bash
   # Test script
   ./.devcontainer/set-project-root.sh
   
   # Test Docker build
   cd .devcontainer && docker-compose build
   
   # Test Node.js availability
   env -i /usr/bin/node --version
   ```

### 📚 Background

This setup addresses these common EC2 devcontainer issues:

1. **Node.js availability**: Devcontainer CLI requires Node.js on the host
2. **Buildx compatibility**: Modern Docker Compose needs buildx 0.17+
3. **Script permissions**: Git doesn't preserve executable permissions
4. **Feature compatibility**: Some third-party features cause JSON parsing issues

The automated setup script handles all these issues automatically.
