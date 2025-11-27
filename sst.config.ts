/// <reference path="./.sst/platform/config.d.ts" />

export default $config({
  app(input) {
    // Use environment variable or default to "DAW" for backward compatibility
    const projectName = process.env.PROJECT_NAME || "DAW";
    return {
      name: projectName,
      removal: input.stage === "prod" ? "retain" : "remove",
      protect: input.stage === "prod",
      home: "aws",
      providers: {
        aws: {
          region: "us-east-1",
        },
      },
    };
  },
  
  async run() {
    // Dynamic imports as required by SST v3
    const { projectConfig, getStageConfig } = await import("./project.config");
    const { createNetwork } = await import("./infra/network");
    const { createDatabase } = await import("./infra/database");
    // NOTE: Not importing createRedisEC2 - using existing manually managed Redis instance
    const { createSyncInfrastructure } = await import("./infra/sync");
    const { SearchAPI } = await import("./infra/search-api");
    
    const stage = $app.stage;
    const stageConfig = getStageConfig(stage);
    
    console.log(`🚀 Deploying ${$app.name} to stage: ${stage}`);
    console.log(`📍 Region: ${stageConfig.region}`);
    console.log(`🔐 Account: ${stageConfig.account}`);
    
    // ===== Network Infrastructure =====
    console.log("🌐 Creating network infrastructure...");
    const network = createNetwork();
    
    // ===== Database Infrastructure =====
    console.log("💾 Creating Aurora MySQL database...");
    const database = createDatabase({
      vpcId: network.vpc.id,
      privateSubnetIds: network.privateSubnets.map(s => s.id),
      securityGroupId: network.rdsSecurityGroup.id,
      stage
    });
    
    // ===== Cache Infrastructure =====
    // Using existing Redis instance (manually managed)
    // Instance: i-0aad9fc4ba71454fa (Debian Redis 8.2.3 with LeanVec4x8)
    // DO NOT create new Redis instance via createRedisEC2()
    console.log("🔴 Using existing Redis Stack 8.2.3 instance...");
    const redisHost = "10.0.11.153";  // i-0aad9fc4ba71454fa
    const redisInstanceId = "i-0aad9fc4ba71454fa";
    
    // ===== Data Sync Infrastructure =====
    console.log("📦 Creating data sync infrastructure...");
    const sync = createSyncInfrastructure(
      network.vpc.id,
      network.privateSubnets.map(s => s.id),
      network.lambdaSecurityGroup.id,
      database.connectionStringParam,
      database.passwordSecretArn,
      database.endpoint,  // DB host (dynamic)
      redisHost           // Redis host (static - existing instance)
    );
    
    // ===== Search API Infrastructure =====
    console.log("🔍 Creating Search API infrastructure...");
    const searchApi = await SearchAPI();
    
    // ===== Outputs =====
    return {
      database: {
        endpoint: database.endpoint,
        port: database.port,
        connectionString: database.connectionStringParam
      },
      redis: {
        endpoint: redisHost,
        port: 6379,
        connectionUrl: `/${$app.name.toLowerCase()}/${stage}/redis/url`,  // Parameter store path
        instanceId: redisInstanceId
      },
      network: {
        vpcId: network.vpc.id,
        lambdaSecurityGroupId: network.lambdaSecurityGroup.id
      },
      sync: {
        functionName: sync.functionName,
        functionArn: sync.functionArn,
        scheduleArn: sync.scheduleArn,
        logGroupName: sync.logGroupName
      },
      searchApi: {
        url: searchApi.api
      }
    };
  },
});

