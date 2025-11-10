/**
 * Database Infrastructure for DAW Drug Search
 * 
 * Creates Aurora MySQL Serverless v2 cluster for FDB data
 * All resources named with "DAW" prefix
 */

import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";

interface DatabaseProps {
  vpcId: pulumi.Output<string>;
  privateSubnetIds: pulumi.Output<string>[];
  securityGroupId: pulumi.Output<string>;
  stage: string;
}

export function createDatabase(props: DatabaseProps) {
  const { vpcId, privateSubnetIds, securityGroupId, stage } = props;

  // DB Subnet Group
  const dbSubnetGroup = new aws.rds.SubnetGroup("DAW-DB-SubnetGroup", {
    name: `daw-db-subnet-${stage}`,  // AWS requires lowercase
    subnetIds: privateSubnetIds,
    tags: {
      Name: `DAW-DB-SubnetGroup-${stage}`,
      Project: "DAW",
      Stage: stage
    }
  });

  // Generate random password for database
  const dbPassword = new aws.secretsmanager.Secret("DAW-DB-Password", {
    name: `DAW-DB-Password-${stage}`,
    description: "Master password for DAW Aurora database",
    tags: {
      Project: "DAW",
      Stage: stage
    }
  });

  const dbPasswordVersion = new aws.secretsmanager.SecretVersion("DAW-DB-PasswordVersion", {
    secretId: dbPassword.id,
    secretString: pulumi.interpolate`{"username":"dawadmin","password":"${pulumi.output(generatePassword())}"}`
  });

  // Aurora MySQL Cluster
  const cluster = new aws.rds.Cluster("DAW-Aurora-Cluster", {
    clusterIdentifier: `daw-aurora-${stage}`,
    engine: "aurora-mysql",
    engineMode: "provisioned",
    engineVersion: "8.0.mysql_aurora.3.04.0",  // Aurora MySQL 8.0 compatible
    databaseName: "daw",
    masterUsername: "dawadmin",
    masterPassword: dbPasswordVersion.secretString.apply(s => JSON.parse(s).password),
    
    // Serverless v2 scaling
    serverlessv2ScalingConfiguration: {
      minCapacity: 0.5,
      maxCapacity: 4
    },
    
    // Network
    dbSubnetGroupName: dbSubnetGroup.name,
    vpcSecurityGroupIds: [securityGroupId],
    
    // Backup
    backupRetentionPeriod: stage === "prod" ? 14 : 7,
    preferredBackupWindow: "03:00-04:00",
    preferredMaintenanceWindow: "sun:04:00-sun:05:00",
    
    // Encryption
    storageEncrypted: true,
    
    // High Availability (multi-AZ for prod)
    availabilityZones: stage === "prod" 
      ? ["us-east-1a", "us-east-1b"]
      : ["us-east-1a"],
    
    skipFinalSnapshot: stage !== "prod",
    finalSnapshotIdentifier: stage === "prod" ? `daw-aurora-final-${stage}` : undefined,
    
    tags: {
      Name: `DAW-Aurora-Cluster-${stage}`,
      Project: "DAW",
      Stage: stage
    }
  });

  // Aurora Cluster Instance (Serverless v2)
  const clusterInstance = new aws.rds.ClusterInstance("DAW-Aurora-Instance", {
    identifier: `daw-aurora-instance-${stage}`,
    clusterIdentifier: cluster.clusterIdentifier,
    instanceClass: "db.serverless",
    engine: "aurora-mysql",
    engineVersion: "8.0.mysql_aurora.3.04.0",  // Match cluster version
    publiclyAccessible: false,
    tags: {
      Name: `DAW-Aurora-Instance-${stage}`,
      Project: "DAW",
      Stage: stage
    }
  });

  // Store connection string in Parameter Store
  const connectionString = pulumi.interpolate`mysql://dawadmin:${dbPasswordVersion.secretString.apply(s => JSON.parse(s).password)}@${cluster.endpoint}:3306/daw`;
  
  const connectionParam = new aws.ssm.Parameter("DAW-DB-ConnectionString", {
    name: `/daw/${stage}/database/connection-string`,
    type: "SecureString",
    value: connectionString,
    description: "DAW Aurora MySQL connection string",
    tags: {
      Project: "DAW",
      Stage: stage
    }
  });

  return {
    cluster,
    clusterInstance,
    endpoint: cluster.endpoint,
    port: cluster.port,
    databaseName: cluster.databaseName,
    passwordSecretArn: dbPassword.arn,
    connectionStringParam: connectionParam.name
  };
}

// Helper function to generate secure random password
function generatePassword(): string {
  const crypto = require('crypto');
  const length = 32;
  const charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=';
  let password = '';
  const randomBytes = crypto.randomBytes(length);
  
  for (let i = 0; i < length; i++) {
    password += charset[randomBytes[i] % charset.length];
  }
  
  return password;
}

