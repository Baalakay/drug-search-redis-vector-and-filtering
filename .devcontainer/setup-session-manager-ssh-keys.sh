#!/bin/bash
# Create SSH keys for Session Manager SSH authentication

echo "🔑 Setting up SSH keys for Session Manager authentication"
echo ""

echo "For your Windows Workspace:"
echo "1. Create SSH key pair in PowerShell:"
echo ""
echo 'ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\session_manager_key" -N ""'
echo ""
echo "2. Update your SSH config to use the key:"
echo ""
echo "Edit D:\\Users\\bmcdonald\\.ssh\\config and change your entry to:"
echo ""
cat << 'EOF'
Host devcontainer-aws-pure
    HostName i-02566fac470923c7c
    User ec2-user
    IdentityFile D:\Users\bmcdonald\.ssh\session_manager_key
    ProxyCommand powershell -Command "$env:PATH += ';C:\\Program Files\\Amazon\\SessionManagerPlugin\\bin'; aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
    IdentitiesOnly yes
    StrictHostKeyChecking no
EOF

echo ""
echo "For your Mac:"
echo "1. Create SSH key pair:"
echo ""
echo 'ssh-keygen -t ed25519 -f ~/.ssh/session_manager_key -N ""'
echo ""
echo "2. Update your SSH config:"
echo ""
cat << 'EOF'
Host ec2-devcontainer
    HostName i-02566fac470923c7c
    User ec2-user
    IdentityFile ~/.ssh/session_manager_key
    ProxyCommand sh -c "aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
    IdentitiesOnly yes
    StrictHostKeyChecking no
EOF

echo ""
echo "🎯 How it works:"
echo "1. SSH client sends the public key to server"
echo "2. Server calls AuthorizedKeysCommand to validate with AWS"
echo "3. AWS Session Manager authenticates the key"
echo "4. Connection succeeds!"
echo ""
echo "⚠️  Important: You don't need to copy the public key anywhere!"
echo "   Session Manager handles the key validation automatically."
echo ""
