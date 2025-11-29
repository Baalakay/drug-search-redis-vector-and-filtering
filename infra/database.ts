/**
 * Database Infrastructure
 * 
 * Creates Aurora MySQL Serverless v2 cluster
 * All resources named with project prefix
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

  // DB Subnet Group - import if it already exists
  const dbSubnetGroup = new aws.rds.SubnetGroup("DAW-DB-SubnetGroup", {
    name: `daw-db-subnet-${stage}`,  // AWS requires lowercase
    subnetIds: privateSubnetIds,
    tags: {
      Name: `DAW-DB-SubnetGroup-${stage}`,
      Project: $app.name,
      Stage: stage
    }
  }, {
    import: `daw-db-subnet-${stage}`
  });

  // Database password secret handling (import existing in dev)
  const secretName = `DAW-DB-Password-${stage}`;
  const shouldImportSecret = stage === "dev";

  let passwordSecretArn: pulumi.Output<string>;
  let passwordSecretString: pulumi.Output<string>;

  if (shouldImportSecret) {
    const existingSecret = aws.secretsmanager.getSecretOutput({ name: secretName });
    const existingSecretVersion = aws.secretsmanager.getSecretVersionOutput({
      secretId: existingSecret.arn
    });

    passwordSecretArn = existingSecret.arn;
    passwordSecretString = existingSecretVersion.secretString!;
  } else {
  const dbPassword = new aws.secretsmanager.Secret("DAW-DB-Password", {
      name: secretName,
    description: "Master password for Aurora database",
    tags: {
      Project: $app.name,
      Stage: stage
    }
  });

  const dbPasswordVersion = new aws.secretsmanager.SecretVersion("DAW-DB-PasswordVersion", {
    secretId: dbPassword.id,
    secretString: pulumi.interpolate`{"username":"dawadmin","password":"${pulumi.output(generatePassword())}"}`
  });

    passwordSecretArn = dbPassword.arn;
    passwordSecretString = dbPasswordVersion.secretString;
  }

  const parsedSecret = passwordSecretString.apply(value => {
    try {
      return JSON.parse(value ?? "{}");
    } catch {
      return {};
    }
  });

  const dbUsername = parsedSecret.apply(data => data.username ?? "dawadmin");
  const dbPasswordValue = parsedSecret.apply(data => data.password ?? "");

  // Reference existing Aurora MySQL Cluster (already deployed)
  const cluster = aws.rds.Cluster.get("DAW-Aurora-Cluster", `daw-aurora-${stage}`);

  // Reference existing Aurora Cluster Instance (Serverless v2)
  const clusterInstance = aws.rds.ClusterInstance.get("DAW-Aurora-Instance", `daw-aurora-instance-${stage}`);

  // Store connection string in Parameter Store
  const appName = pulumi.output($app.name).apply(n => n.toLowerCase());
  const connectionString = pulumi.interpolate`mysql://${dbUsername}:${dbPasswordValue}@${cluster.endpoint}:3306/${appName}`;
  
  const connectionParam = new aws.ssm.Parameter("DAW-DB-ConnectionString", {
    name: pulumi.interpolate`/${appName}/${stage}/database/connection-string`,
    type: "SecureString",
    value: connectionString,
    description: `${$app.name} Aurora MySQL connection string`,
    overwrite: true,
    tags: {
      Project: $app.name,
      Stage: stage
    }
  });

  return {
    cluster,
    clusterInstance,
    endpoint: cluster.endpoint,
    port: cluster.port,
    databaseName: cluster.databaseName,
    passwordSecretArn,
    connectionStringParam: connectionParam.name
  };
}

// Helper function to generate secure random password
function generatePassword(): string {
  const crypto = require('crypto');
  const length = 32;
  // Aurora MySQL doesn't allow: / @ " ' (space)
  // Safe characters: letters, numbers, and: ! # $ % ^ & * ( ) _ + - =
  const charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%^&*()_+-=';
  let password = '';
  const randomBytes = crypto.randomBytes(length);
  
  for (let i = 0; i < length; i++) {
    password += charset[randomBytes[i] % charset.length];
  }
  
  return password;
}

