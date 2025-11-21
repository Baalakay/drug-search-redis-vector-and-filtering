/**
 * Redis Infrastructure for DAW Drug Search
 * 
 * Deploys self-managed Redis 8.2.3 on EC2 x86 (r7i.large)
 * Supports LeanVec4x8 quantization and RediSearch hybrid search
 * All resources named with "DAW" prefix
 * 
 * NOTE: Switched from ARM Graviton to x86 due to Redis Stack ARM binary incompatibility
 */

import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";

interface RedisProps {
  vpcId: pulumi.Output<string>;
  privateSubnetIds: pulumi.Output<string>[];
  securityGroupId: pulumi.Output<string>;
  stage: string;
}

export function createRedisEC2(props: RedisProps) {
  const { vpcId, privateSubnetIds, securityGroupId, stage } = props;

  // Generate auth token for Redis
  const authToken = new aws.secretsmanager.Secret("DAW-Redis-AuthToken", {
    name: `DAW-Redis-AuthToken-${stage}`,
    description: "Auth token for DAW Redis instance",
    tags: {
      Project: "DAW",
      Stage: stage
    }
  });

  const authTokenValue = new aws.secretsmanager.SecretVersion("DAW-Redis-AuthTokenVersion", {
    secretId: authToken.id,
    secretString: pulumi.output(generateAuthToken())
  });

  // Get latest Ubuntu 22.04 x86_64 AMI
  const ubuntuAmi = aws.ec2.getAmi({
    mostRecent: true,
    owners: ["099720109477"], // Canonical
    filters: [
      {
        name: "name",
        values: ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
      },
      {
        name: "virtualization-type",
        values: ["hvm"]
      }
    ]
  });

  // IAM Role for Redis instance (for CloudWatch, SSM, snapshots)
  const redisRole = new aws.iam.Role("DAW-Redis-InstanceRole", {
    name: `DAW-Redis-InstanceRole-${stage}`,
    assumeRolePolicy: JSON.stringify({
      Version: "2012-10-17",
      Statement: [{
        Action: "sts:AssumeRole",
        Effect: "Allow",
        Principal: {
          Service: "ec2.amazonaws.com"
        }
      }]
    }),
    tags: {
      Name: `DAW-Redis-InstanceRole-${stage}`,
      Project: "DAW"
    }
  });

  // Attach policies for CloudWatch, SSM, and EBS snapshots
  new aws.iam.RolePolicyAttachment("DAW-Redis-CloudWatchPolicy", {
    role: redisRole.name,
    policyArn: "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
  });

  new aws.iam.RolePolicyAttachment("DAW-Redis-SSMPolicy", {
    role: redisRole.name,
    policyArn: "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  });

  // Custom policy for EBS snapshots, S3 access, Secrets Manager, and Bedrock
  const snapshotPolicy = new aws.iam.Policy("DAW-Redis-SnapshotPolicy", {
    name: `DAW-Redis-SnapshotPolicy-${stage}`,
    policy: JSON.stringify({
      Version: "2012-10-17",
      Statement: [
        {
          Effect: "Allow",
          Action: [
            "ec2:CreateSnapshot",
            "ec2:DeleteSnapshot",
            "ec2:DescribeSnapshots",
            "ec2:CreateTags"
          ],
          Resource: "*"
        },
        {
          Effect: "Allow",
          Action: [
            "s3:GetObject",
            "s3:ListBucket"
          ],
          Resource: [
            "arn:aws:s3:::daw-temp-data-import-*",
            "arn:aws:s3:::daw-temp-data-import-*/*"
          ]
        },
        {
          Effect: "Allow",
          Action: [
            "secretsmanager:GetSecretValue"
          ],
          Resource: [
            `arn:aws:secretsmanager:*:*:secret:DAW-AuroraDBCredentials-${stage}-*`,
            `arn:aws:secretsmanager:*:*:secret:DAW-Redis-AuthToken-${stage}-*`
          ]
        },
        {
          Effect: "Allow",
          Action: [
            "bedrock:InvokeModel"
          ],
          Resource: "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
        }
      ]
    }),
    tags: {
      Project: "DAW"
    }
  });

  new aws.iam.RolePolicyAttachment("DAW-Redis-SnapshotPolicyAttachment", {
    role: redisRole.name,
    policyArn: snapshotPolicy.arn
  });

  // Instance profile
  const instanceProfile = new aws.iam.InstanceProfile("DAW-Redis-InstanceProfile", {
    name: `DAW-Redis-InstanceProfile-${stage}`,
    role: redisRole.name,
    tags: {
      Project: "DAW"
    }
  });

  // User data script to install and configure Redis Stack 8.2.2
  const userData = pulumi.all([authTokenValue.secretString]).apply(([token]) => `#!/bin/bash
set -e
exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "Starting Redis Stack 7.4.0 installation on Ubuntu 22.04..."

# Update system
apt-get update
apt-get upgrade -y

# Install dependencies (including for bulk load scripts)
export DEBIAN_FRONTEND=noninteractive
apt-get install -y curl gpg lsb-release python3-pip python3-mysql.connector awscli

# Install latest boto3 and redis via pip (Ubuntu packages too old)
# boto3: Ubuntu has 1.20.34, need >= 1.28.0 for bedrock-runtime
# redis: Ubuntu has 3.5.3, need >= 4.0.0 for better password handling
pip3 install boto3 redis --upgrade

# Add official Redis repository for Redis Stack on x86
curl -fsSL https://packages.redis.io/gpg | gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/redis.list

# Install Redis Stack (includes Redis 7.4 + RediSearch 2.10+ with LeanVec4x8, RedisJSON, etc.)
apt-get update
apt-get install -y redis-stack-server

# Verify installation
/opt/redis-stack/bin/redis-server --version
/opt/redis-stack/bin/redis-cli --version

# Create Redis configuration with LeanVec4x8 quantization support
cat > /etc/redis-stack.conf <<'EOF'
# Network
bind 0.0.0.0
port 6379
protected-mode yes
requirepass ${token}
tcp-backlog 511
timeout 0
tcp-keepalive 300

# Memory
maxmemory 12gb
maxmemory-policy allkeys-lru

# Persistence (AOF for durability)
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
no-appendfsync-on-rewrite no
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# RDB Snapshots (backup)
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir /var/lib/redis-stack

# Logging
loglevel notice
logfile /var/log/redis/redis-stack-server.log

# Performance
slowlog-log-slower-than 10000
slowlog-max-len 128

# Security
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG DAW-CONFIG-PROTECTED

# RediSearch Module (included in Redis Stack)
# Modules loaded automatically by Redis Stack (redisearch.so, rejson.so, etc.)
# RediSearch 2.10+ includes LeanVec4x8 quantization support

# Limits
maxclients 10000
EOF

# Redis user already created by apt package, just ensure permissions
mkdir -p /var/lib/redis /var/log/redis
chown -R redis:redis /var/lib/redis /var/log/redis /etc/redis-stack.conf
chmod 640 /etc/redis-stack.conf

# Stop default Redis service (we'll use our custom config)
systemctl stop redis-server 2>/dev/null || true
systemctl disable redis-server 2>/dev/null || true

# Create custom systemd service for Redis Stack
cat > /etc/systemd/system/redis-daw.service <<'SVCEOF'
[Unit]
Description=Redis Stack 7.4 with RediSearch (LeanVec4x8) and RedisJSON
After=network.target

[Service]
Type=simple
User=redis
Group=redis
ExecStart=/opt/redis-stack/bin/redis-server /etc/redis-stack.conf --loadmodule /opt/redis-stack/lib/redisearch.so --loadmodule /opt/redis-stack/lib/rejson.so
Restart=always
RestartSec=3
LimitNOFILE=65536
WorkingDirectory=/var/lib/redis-stack

[Install]
WantedBy=multi-user.target
SVCEOF

# Enable and start Redis
systemctl daemon-reload
systemctl enable redis-daw
systemctl start redis-daw

# Wait for Redis to start
sleep 5

# Verify Redis is running
if systemctl is-active --quiet redis-daw; then
  echo "✅ Redis Stack 7.4 with RediSearch (LeanVec4x8) started successfully on x86"
  /opt/redis-stack/bin/redis-cli --no-auth-warning -a ${token} PING
  /opt/redis-stack/bin/redis-cli --no-auth-warning -a ${token} INFO server | grep redis_version
  /opt/redis-stack/bin/redis-cli --no-auth-warning -a ${token} MODULE LIST
else
  echo "❌ Redis failed to start"
  systemctl status redis-daw
  journalctl -u redis-daw -n 50
  exit 1
fi

# Install CloudWatch agent (Ubuntu x86_64 uses DEB)
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
dpkg -i -E ./amazon-cloudwatch-agent.deb
rm ./amazon-cloudwatch-agent.deb

# Configure CloudWatch agent
cat > /opt/aws/amazon-cloudwatch-agent/etc/config.json <<'CWEOF'
{
  "metrics": {
    "namespace": "DAW/Redis",
    "metrics_collected": {
      "mem": {
        "measurement": [
          {"name": "mem_used_percent", "rename": "MemoryUsedPercent", "unit": "Percent"}
        ],
        "metrics_collection_interval": 60
      },
      "disk": {
        "measurement": [
          {"name": "used_percent", "rename": "DiskUsedPercent", "unit": "Percent"}
        ],
        "metrics_collection_interval": 60,
        "resources": ["*"]
      }
    }
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/redis/redis-stack-server.log",
            "log_group_name": "/daw/${stage}/redis",
            "log_stream_name": "{instance_id}"
          }
        ]
      }
    }
  }
}
CWEOF

# Start CloudWatch agent
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config \
  -m ec2 \
  -s \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/config.json

# Setup automated snapshots (cron)
cat > /usr/local/bin/redis-snapshot.sh <<'SNAPEOF'
#!/bin/bash
VOLUME_ID=$(aws ec2 describe-instances --instance-ids $(ec2-metadata --instance-id | cut -d " " -f 2) --query "Reservations[0].Instances[0].BlockDeviceMappings[0].Ebs.VolumeId" --output text)
DATE=$(date +%Y%m%d-%H%M%S)

aws ec2 create-snapshot \
  --volume-id $VOLUME_ID \
  --description "DAW-Redis-Backup-$DATE" \
  --tag-specifications "ResourceType=snapshot,Tags=[{Key=Project,Value=DAW},{Key=Stage,Value=${stage}},{Key=Type,Value=Automated}]"

# Clean up old snapshots (keep last 7 days)
aws ec2 describe-snapshots \
  --filters "Name=tag:Project,Values=DAW" "Name=tag:Type,Values=Automated" \
  --query "Snapshots[?StartTime<='$(date -d '7 days ago' --iso-8601=seconds)'].SnapshotId" \
  --output text | xargs -n 1 aws ec2 delete-snapshot --snapshot-id
SNAPEOF

chmod +x /usr/local/bin/redis-snapshot.sh

# Add to cron (daily at 3 AM)
echo "0 3 * * * /usr/local/bin/redis-snapshot.sh >> /var/log/redis-snapshots.log 2>&1" | crontab -

echo "Redis Stack 8.2.2 installation complete!"
`);

  // Redis EC2 Instance
  const redisInstance = new aws.ec2.Instance("DAW-Redis-Server", {
    ami: ubuntuAmi.then(ami => ami.id),
    instanceType: "r7i.large",  // x86 (Intel), 2 vCPU, 16 GB RAM
    
    // Network
    subnetId: privateSubnetIds[0],  // Private subnet
    vpcSecurityGroupIds: [securityGroupId],
    
    // Storage
    rootBlockDevice: {
      volumeSize: 50,  // 50 GB
      volumeType: "gp3",
      encrypted: true,
      deleteOnTermination: stage !== "prod"
    },
    
    // IAM
    iamInstanceProfile: instanceProfile.name,
    
    // User data
    userData: userData,
    
    // Monitoring
    monitoring: true,
    
    // Tags
    tags: {
      Name: `DAW-Redis-Server-${stage}`,
      Project: "DAW",
      Stage: stage,
      Component: "Cache",
      RedisVersion: "8.2.2"
    }
  });

  // CloudWatch Log Group
  const logGroup = new aws.cloudwatch.LogGroup("DAW-Redis-LogGroup", {
    name: `/daw/${stage}/redis`,
    retentionInDays: stage === "prod" ? 30 : 7,
    tags: {
      Project: "DAW",
      Stage: stage
    }
  });

  // CloudWatch Alarms
  new aws.cloudwatch.MetricAlarm("DAW-Redis-HighCPU", {
    name: `DAW-Redis-HighCPU-${stage}`,
    comparisonOperator: "GreaterThanThreshold",
    evaluationPeriods: 2,
    metricName: "CPUUtilization",
    namespace: "AWS/EC2",
    period: 300,
    statistic: "Average",
    threshold: 80,
    alarmDescription: "Redis CPU usage is high",
    dimensions: {
      InstanceId: redisInstance.id
    },
    tags: {
      Project: "DAW",
      Stage: stage
    }
  });

  new aws.cloudwatch.MetricAlarm("DAW-Redis-HighMemory", {
    name: `DAW-Redis-HighMemory-${stage}`,
    comparisonOperator: "GreaterThanThreshold",
    evaluationPeriods: 2,
    metricName: "MemoryUsedPercent",
    namespace: "DAW/Redis",
    period: 300,
    statistic: "Average",
    threshold: 90,
    alarmDescription: "Redis memory usage is high",
    tags: {
      Project: "DAW",
      Stage: stage
    }
  });

  // Store connection details in Parameter Store
  const redisHost = redisInstance.privateIp;
  
  const redisUrlParam = new aws.ssm.Parameter("DAW-Redis-URL", {
    name: `/daw/${stage}/redis/url`,
    type: "SecureString",
    value: pulumi.interpolate`redis://:${authTokenValue.secretString}@${redisHost}:6379`,
    description: "DAW Redis connection URL",
    tags: {
      Project: "DAW",
      Stage: stage
    }
  });

  const redisHostParam = new aws.ssm.Parameter("DAW-Redis-Host", {
    name: `/daw/${stage}/redis/host`,
    type: "String",
    value: redisHost,
    description: "DAW Redis host IP",
    tags: {
      Project: "DAW",
      Stage: stage
    }
  });

  return {
    instance: redisInstance,
    endpoint: redisHost,
    port: pulumi.output(6379),
    authTokenSecretArn: authToken.arn,
    redisUrlParam: redisUrlParam.name,
    redisHostParam: redisHostParam.name,
    logGroup: logGroup.name
  };
}

// Helper function to generate secure auth token
function generateAuthToken(): string {
  const crypto = require('crypto');
  const length = 32;
  const charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let token = '';
  const randomBytes = crypto.randomBytes(length);
  
  for (let i = 0; i < length; i++) {
    token += charset[randomBytes[i] % charset.length];
  }
  
  return token;
}

