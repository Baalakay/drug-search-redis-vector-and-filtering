/// <reference path="../.sst/platform/config.d.ts" />

/**
 * Data Sync Infrastructure
 * 
 * Lambda function to sync drugs from Aurora MySQL to Redis with embeddings.
 * Scheduled to run daily via EventBridge.
 * 
 * CRITICAL: Using sst.aws.Function instead of raw aws.lambda.Function
 * for proper SST packaging and dependency management.
 */

import * as aws from "@pulumi/aws";
import * as pulumi from "@pulumi/pulumi";

const stage = $app.stage;

export function createSyncInfrastructure(
  vpcId: string | pulumi.Output<string>,
  privateSubnetIds: string[] | pulumi.Output<string>[],
  lambdaSecurityGroupId: string | pulumi.Output<string>,
  dbConnectionStringParam: string | pulumi.Output<string>,
  dbSecretArn: string | pulumi.Output<string>,
  dbHost: string | pulumi.Output<string>,
  redisHost: string
) {
  console.log("📦 Creating Data Sync infrastructure...");

  // Get VPC for Lambda
  const vpc = aws.ec2.Vpc.get("DAW-VPC-Lookup", vpcId);

  /**
   * Determine existing resource identifiers for dev (imported via SST docs Issue #0)
   */
  const accountId = process.env.AWS_ACCOUNT_ID ?? "750389970429";

  /**
   * IAM Role for Lambda Function
   */
  const roleOpts = stage === "dev"
    ? ({ import: `DAW-DrugSync-Role-${stage}` } as pulumi.CustomResourceOptions)
    : undefined;

  const lambdaRole = new aws.iam.Role("DAW-DrugSync-Role", {
    name: `DAW-DrugSync-Role-${stage}`,
    assumeRolePolicy: JSON.stringify({
      Version: "2012-10-17",
      Statement: [{
        Effect: "Allow",
        Principal: { Service: "lambda.amazonaws.com" },
        Action: "sts:AssumeRole",
      }],
    }),
    tags: {
      Name: `${$app.name}-DrugSync-Role-${stage}`,
      Project: $app.name,
      Component: "Sync",
    },
  }, roleOpts);

  // Attach basic Lambda execution policy (for CloudWatch Logs)
  const lambdaBasicPolicy = new aws.iam.RolePolicyAttachment("DAW-DrugSync-BasicPolicy", {
    role: lambdaRole.name,
    policyArn: "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole",
  });

  /**
   * Lambda Function for Drug Sync
   * 
   * Using SST's native Function construct for proper packaging
   * Import existing function to avoid conflicts
   */
  const syncFunction = new sst.aws.Function("DAW-DrugSync-Function", {
    name: `DAW-DrugSync-${stage}`,
    description: "Sync drugs from Aurora to Redis with Bedrock embeddings",
    handler: "functions.src.handlers.drug_loader.lambda_handler",
    runtime: "python3.12",
    timeout: "15 minutes",
    memory: "1 GB",
    vpc: {
      securityGroups: [lambdaSecurityGroupId],
      privateSubnets: privateSubnetIds,  // Fixed: was "subnets", now "privateSubnets"
    },
    
    environment: {
      DB_HOST: dbHost,
      DB_PORT: "3306",
      DB_NAME: "fdb",
      DB_SECRET_ARN: dbSecretArn,
      REDIS_HOST: redisHost,
      REDIS_PORT: "6379",
      BATCH_SIZE: "100",
      MAX_DRUGS: "0",
      ENABLE_QUANTIZATION: "true",
      EMBEDDING_MODEL: "titan",
    },
    
    permissions: [
      {
        actions: ["bedrock:InvokeModel"],
        resources: ["*"],
      },
      {
        actions: ["secretsmanager:GetSecretValue"],
        resources: [dbSecretArn],
      },
    ],
    
    tags: {
      Name: `${$app.name}-DrugSync-${stage}`,
      Project: $app.name,
      Component: "Sync",
      Stage: stage,
    },
  });

  /**
   * Additional IAM Policies
   */
  
  // Bedrock permissions for embeddings
  const bedrockPolicy = new aws.iam.RolePolicy("DAW-DrugSync-BedrockPolicy", {
    role: lambdaRole.name,
    policy: JSON.stringify({
      Version: "2012-10-17",
      Statement: [
        {
          Effect: "Allow",
          Action: [
            "bedrock:InvokeModel",
          ],
          Resource: [
            "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0",
            "arn:aws:bedrock:*:*:inference-profile/us.anthropic.claude-sonnet-4-0",
          ],
        },
      ],
    }),
  });

  // Secrets Manager permissions for DB credentials
  const secretsPolicy = new aws.iam.RolePolicy("DAW-DrugSync-SecretsPolicy", {
    role: lambdaRole.name,
    policy: {
      Version: "2012-10-17",
      Statement: [{
        Effect: "Allow",
        Action: "secretsmanager:GetSecretValue",
        Resource: dbSecretArn,
      }],
    },
  });

  // CloudWatch Logs permissions (auto-created but explicit for clarity)
  const logsPolicy = new aws.iam.RolePolicy("DAW-DrugSync-LogsPolicy", {
    role: lambdaRole.name,
    policy: JSON.stringify({
      Version: "2012-10-17",
      Statement: [
        {
          Effect: "Allow",
          Action: [
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:PutLogEvents",
          ],
          Resource: `arn:aws:logs:us-east-1:*:log-group:/aws/lambda/DAW-DrugSync-${stage}:*`,
        },
      ],
    }),
  });

  // CloudWatch Metrics permissions
  const metricsPolicy = new aws.iam.RolePolicy("DAW-DrugSync-MetricsPolicy", {
    role: lambdaRole.name,
    policy: JSON.stringify({
      Version: "2012-10-17",
      Statement: [
        {
          Effect: "Allow",
          Action: [
            "cloudwatch:PutMetricData",
          ],
          Resource: "*",
          Condition: {
            StringEquals: {
              "cloudwatch:namespace": `${$app.name}/DrugSync`,
            },
          },
        },
      ],
    }),
  });

  /**
   * EventBridge Rule for Daily Sync
   */
  const syncSchedule = new aws.cloudwatch.EventRule("DAW-DrugSync-Schedule", {
    name: `DAW-DrugSync-Schedule-${stage}`,
    description: "Trigger drug sync daily at 2 AM UTC",
    scheduleExpression: "cron(0 2 * * ? *)", // Daily at 2 AM UTC
    state: "ENABLED",
    tags: {
      Name: `DAW-DrugSync-Schedule-${stage}`,
      Project: "DAW",
    },
  });

  // Permission for EventBridge to invoke Lambda
  const lambdaPermission = new aws.lambda.Permission("DAW-DrugSync-EventPermission", {
    action: "lambda:InvokeFunction",
    function: syncFunction.name,
    principal: "events.amazonaws.com",
    sourceArn: syncSchedule.arn,
  });

  // EventBridge target
  const syncTarget = new aws.cloudwatch.EventTarget("DAW-DrugSync-Target", {
    rule: syncSchedule.name,
    arn: syncFunction.arn,
    input: JSON.stringify({
      batch_size: 100,
      max_drugs: 0, // Sync all drugs
    }),
  });

  /**
   * CloudWatch Alarms
   */
  
  // Alarm for sync failures
  const failureAlarm = new aws.cloudwatch.MetricAlarm("DAW-DrugSync-FailureAlarm", {
    name: `DAW-DrugSync-Failures-${stage}`,
    comparisonOperator: "GreaterThanThreshold",
    evaluationPeriods: 1,
    metricName: "DrugsFailed",
    namespace: "DAW/DrugSync",
    period: 3600, // 1 hour
    statistic: "Sum",
    threshold: 100, // Alert if > 100 drugs fail
    treatMissingData: "notBreaching",
    alarmDescription: "Alert when drug sync has > 100 failures",
    tags: {
      Name: `DAW-DrugSync-FailureAlarm-${stage}`,
      Project: "DAW",
    },
  });

  // Alarm for Lambda errors
  const errorAlarm = new aws.cloudwatch.MetricAlarm("DAW-DrugSync-ErrorAlarm", {
    name: `DAW-DrugSync-Errors-${stage}`,
    comparisonOperator: "GreaterThanThreshold",
    evaluationPeriods: 1,
    metricName: "Errors",
    namespace: "AWS/Lambda",
    dimensions: {
      FunctionName: syncFunction.name,
    },
    period: 300, // 5 minutes
    statistic: "Sum",
    threshold: 0, // Alert on any error
    treatMissingData: "notBreaching",
    alarmDescription: "Alert when drug sync Lambda errors",
    tags: {
      Name: `DAW-DrugSync-ErrorAlarm-${stage}`,
      Project: "DAW",
    },
  });

  console.log("   ✅ Drug sync infrastructure created");

  return {
    functionName: syncFunction.name,
    functionArn: syncFunction.arn,
    scheduleArn: syncSchedule.arn,
    logGroupName: pulumi.interpolate`/aws/lambda/${syncFunction.name}`,
    function: syncFunction, // Return full function for SST outputs
  };
}

