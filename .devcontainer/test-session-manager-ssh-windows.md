# Test Session Manager SSH from Windows Workspace

Let's test pure Session Manager SSH from your Windows Workspace to isolate the issue.

## 🧪 Test 1: Update Windows SSH Config for Pure Session Manager

**Edit your `D:\Users\bmcdonald\.ssh\config` on Windows Workspace:**

Change from this (current with PEM):
```ssh
Host devcontainer-aws
    HostName i-02566fac470923c7c
    User ec2-user
    IdentityFile D:\Users\bmcdonald\Documents\projects\DAW\devcontainer-key.pem
    ProxyCommand powershell -Command "$env:PATH += ';C:\Program Files\Amazon\SessionManagerPlugin\bin'; aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
    StrictHostKeyChecking no
    ServerAliveInterval 60
    ServerAliveCountMax 3
    LocalForward 2376 127.0.0.1:2376
```

To this (pure Session Manager):
```ssh
Host devcontainer-aws-pure
    HostName i-02566fac470923c7c
    User ec2-user
    ProxyCommand powershell -Command "$env:PATH += ';C:\Program Files\Amazon\SessionManagerPlugin\bin'; aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
    IdentitiesOnly yes
    StrictHostKeyChecking no
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

## 🧪 Test 2: Try Pure Session Manager SSH from Windows

```cmd
ssh devcontainer-aws-pure
```

## 🔍 Expected Results:

**If it works from Windows:**
- ✅ EC2 Session Manager SSH is configured correctly
- ❌ Issue is with Mac setup (AWS CLI, Session Manager plugin, or config)

**If it fails from Windows with same error:**
- ❌ EC2 Session Manager SSH configuration issue
- ✅ Not a Mac-specific problem

## 🧪 Test 3: Alternative User Test

If ec2-user fails, try with ssm-user from Windows:

```ssh
Host devcontainer-aws-ssm
    HostName i-02566fac470923c7c
    User ssm-user
    ProxyCommand powershell -Command "$env:PATH += ';C:\Program Files\Amazon\SessionManagerPlugin\bin'; aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
    IdentitiesOnly yes
```

```cmd
ssh devcontainer-aws-ssm
```

## 📋 Report Back:

Please test these and let me know:
1. **Does pure Session Manager SSH work from Windows Workspace?** (Test 2)
2. **Does it work with ssm-user from Windows?** (Test 3)
3. **What exact error do you get?**

This will tell us if we need to:
- Fix EC2 Session Manager SSH configuration, OR  
- Fix Mac-specific setup issues
