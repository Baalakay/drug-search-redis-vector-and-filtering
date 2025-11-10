# Mac SSH Workaround - Working Solution

Since Session Manager SSH with ec2-user isn't working as expected, here's a practical workaround using ssm-user:

## 🔧 Update Your Mac SSH Config

Replace your current `~/.ssh/config` entry with:

```ssh
Host ec2-devcontainer
    HostName i-02566fac470923c7c
    ProxyCommand sh -c "aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p'"
    User ssm-user
    IdentitiesOnly yes
```

## 🚀 Usage

### Connect to EC2:
```bash
# SSH to instance as ssm-user
ssh ec2-devcontainer

# Switch to ec2-user (has sudo access)
sudo su - ec2-user
```

### Copy Files:
```bash
# Copy files to ssm-user's home, then move them
scp -r ~/.aws/ ec2-devcontainer:~/

# Then SSH in and move files:
ssh ec2-devcontainer
sudo cp -r ~/.aws/ /home/ec2-user/
sudo chown -R ec2-user:ec2-user /home/ec2-user/.aws
sudo su - ec2-user
```

## 📁 One-Command File Copy Script

Create this script on your Mac to simplify transfers:

```bash
#!/bin/bash
# save as ~/bin/copy-to-ec2.sh
scp -r "$1" ec2-devcontainer:~/temp-upload/
ssh ec2-devcontainer "sudo cp -r ~/temp-upload/* /home/ec2-user/ && sudo chown -R ec2-user:ec2-user /home/ec2-user/* && rm -rf ~/temp-upload"
```

Usage:
```bash
chmod +x ~/bin/copy-to-ec2.sh
~/bin/copy-to-ec2.sh ~/.aws
```
