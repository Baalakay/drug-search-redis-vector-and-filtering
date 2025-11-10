/**
 * Redis Infrastructure for DAW Drug Search
 * 
 * Deploys self-managed Redis Stack 8.2.2 on EC2 ARM Graviton3
 * Supports LeanVec4x8 quantization and RediSearch hybrid search
 * All resources named with "DAW" prefix
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

  // Get latest Ubuntu 22.04 ARM64 AMI
  const ubuntuAmi = aws.ec2.getAmi({
    mostRecent: true,
    owners: ["099720109477"], // Canonical
    filters: [
      {
        name: "name",
        values: ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-arm64-server-*"]
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

  // Custom policy for EBS snapshots, S3 access, and Secrets Manager
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
          Resource: `arn:aws:secretsmanager:*:*:secret:DAW-DB-Password-${stage}-*`
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

# Update system
apt-get update
apt-get upgrade -y

# Install dependencies
apt-get install -y curl gpg lsb-release

# Add Redis repository
curl -fsSL https://packages.redis.io/gpg | gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
echo "deb [arch=arm64 signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/redis.list

# Install Redis Stack 8.2.2 (latest stable)
apt-get update
apt-get install -y redis-stack-server

# Create Redis configuration
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
loadmodule /opt/redis-stack/lib/redisearch.so

# Limits
maxclients 10000
EOF

# Set proper ownership
chown redis:redis /etc/redis-stack.conf
chmod 640 /etc/redis-stack.conf

# Create data directory
mkdir -p /var/lib/redis-stack
chown -R redis:redis /var/lib/redis-stack

# Create log directory
mkdir -p /var/log/redis
chown -R redis:redis /var/log/redis

# Update systemd service to use our config
cat > /etc/systemd/system/redis-stack-server.service <<'EOF'
[Unit]
Description=Redis Stack Server
After=network.target

[Service]
Type=notify
ExecStart=/opt/redis-stack/bin/redis-stack-server /etc/redis-stack.conf
ExecStop=/bin/kill -s TERM $MAINPID
PIDFile=/var/run/redis/redis-stack-server.pid
TimeoutStopSec=0
Restart=always
User=redis
Group=redis
RuntimeDirectory=redis
RuntimeDirectoryMode=2755

LimitNOFILE=65535
LimitNPROC=65535

[Install]
WantedBy=multi-user.target
EOF

# Enable and start Redis
systemctl daemon-reload
systemctl enable redis-stack-server
systemctl start redis-stack-server

# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/arm64/latest/amazon-cloudwatch-agent.deb
dpkg -i -E ./amazon-cloudwatch-agent.deb

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
    instanceType: "r7g.large",  // ARM Graviton3, 2 vCPU, 16 GB RAM
    
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

