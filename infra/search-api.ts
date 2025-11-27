/// <reference path="../.sst/platform/config.d.ts" />

/**
 * Search API Infrastructure
 * 
 * API Gateway with Lambda functions for drug search endpoints.
 * Uses separate sst.aws.Function definitions for proper SST packaging.
 */

export function SearchAPI() {
  const accountId = process.env.AWS_ACCOUNT_ID ?? "750389970429";
  
  // Environment variables (use values from deployed infrastructure)
  const vpcId = process.env.VPC_ID || "vpc-050fab8a9258195b7";
  const privateSubnetIds = [
    process.env.PRIVATE_SUBNET_1 || "subnet-05ea4d85ade4340db",
    process.env.PRIVATE_SUBNET_2 || "subnet-07c025dd82ff8355e"
  ];
  
  const lambdaSecurityGroupId = process.env.LAMBDA_SECURITY_GROUP_ID || "sg-0e78f3a483550e499";
  
  const redisHost = process.env.REDIS_HOST || "10.0.11.153";
  const redisPassword = process.env.REDIS_PASSWORD || "DAW-Redis-SecureAuth-2025";
  
  /**
   * Lambda Functions (SST Native Constructs)
   */
  const searchFunction = new sst.aws.Function("SearchFunction", {
    handler: "functions.src.search_handler.lambda_handler",
    runtime: "python3.12",
    timeout: "30 seconds",
    memory: "1024 MB",  // Increased for 2x CPU power + faster execution
    provisionedConcurrency: 1,  // Pre-warm 1 instance to eliminate cold starts
    vpc: {
      privateSubnets: privateSubnetIds,
      securityGroups: [lambdaSecurityGroupId]
    },
    environment: {
      REDIS_HOST: redisHost,
      REDIS_PORT: "6379",
      REDIS_PASSWORD: redisPassword,
      BEDROCK_REGION: "us-east-1",
      // NO MODEL IDS HERE - llm_config.py is the single source of truth!
      CLAUDE_MAX_TOKENS: "1000",
      CLAUDE_TEMPERATURE: "0",
    },
    permissions: [
      {
        actions: [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:Converse",
          "bedrock:ConverseStream"
        ],
        resources: [
          "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
          "arn:aws:bedrock:*::foundation-model/amazon.nova-*",
          "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-*",
          "arn:aws:bedrock:::foundation-model/anthropic.claude-*",
          "arn:aws:bedrock:::foundation-model/amazon.titan-*",
          `arn:aws:bedrock:us-east-1:${accountId}:inference-profile/*`
        ]
      },
      {
        actions: ["cloudwatch:PutMetricData"],
        resources: ["*"]
      }
    ]
  });
  
  const alternativesFunction = new sst.aws.Function("AlternativesFunction", {
    handler: "functions.src.alternatives_handler.lambda_handler",
    runtime: "python3.12",
    timeout: "10 seconds",
    memory: "256 MB",
    vpc: {
      privateSubnets: privateSubnetIds,
      securityGroups: [lambdaSecurityGroupId]
    },
    environment: {
      REDIS_HOST: redisHost,
      REDIS_PORT: "6379",
      REDIS_PASSWORD: redisPassword
    },
    permissions: [
      {
        actions: ["secretsmanager:GetSecretValue"],
        resources: [`arn:aws:secretsmanager:us-east-1:*:secret:${$app.name}-Redis-AuthToken-*`]
      }
    ]
  });
  
  const drugDetailFunction = new sst.aws.Function("DrugDetailFunction", {
    handler: "functions.src.drug_detail_handler.lambda_handler",
    runtime: "python3.12",
    timeout: "10 seconds",
    memory: "256 MB",
    vpc: {
      privateSubnets: privateSubnetIds,
      securityGroups: [lambdaSecurityGroupId]
    },
    environment: {
      REDIS_HOST: redisHost,
      REDIS_PORT: "6379",
      REDIS_PASSWORD: redisPassword
    },
    permissions: [
      {
        actions: ["secretsmanager:GetSecretValue"],
        resources: [`arn:aws:secretsmanager:us-east-1:*:secret:${$app.name}-Redis-AuthToken-*`]
      }
    ]
  });
  
  /**
   * API Gateway with Routes
   */
  const api = new sst.aws.ApiGatewayV2("DrugSearchAPI", {
    cors: {
      allowOrigins: ["*"],
      allowMethods: ["GET", "POST", "OPTIONS"],
      allowHeaders: ["Content-Type", "Authorization"]
    }
  });
  
  // Link functions to routes
  api.route("POST /search", searchFunction.arn);
  api.route("GET /drugs/{ndc}/alternatives", alternativesFunction.arn);
  api.route("GET /drugs/{ndc}", drugDetailFunction.arn);
  
  return {
    api: api.url,
    functions: {
      search: searchFunction.name,
      alternatives: alternativesFunction.name,
      drugDetail: drugDetailFunction.name
    }
  };
}
