/// <reference path="./.sst/platform/config.d.ts" />

export default $config({
  app(input) {
    return {
      name: "DAW",
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
    const { createRedisEC2 } = await import("./infra/redis-ec2");
    
    const stage = $app.stage;
    const stageConfig = getStageConfig(stage);
    
    console.log(`🚀 Deploying DAW to stage: ${stage}`);
    console.log(`📍 Region: ${stageConfig.region}`);
    console.log(`🔐 Account: ${stageConfig.account}`);
    
    // ===== Network Infrastructure =====
    console.log("🌐 Creating network infrastructure...");
    const network = createNetwork();
    
    // ===== Database Infrastructure =====
    console.log("💾 Creating Aurora PostgreSQL database...");
    const database = createDatabase({
      vpcId: network.vpc.id,
      privateSubnetIds: network.privateSubnets.map(s => s.id),
      securityGroupId: network.rdsSecurityGroup.id,
      stage
    });
    
    // ===== Cache Infrastructure =====
    console.log("🔴 Creating Redis Stack 8.2.2 on EC2 (ARM Graviton3)...");
    const redis = createRedisEC2({
      vpcId: network.vpc.id,
      privateSubnetIds: network.privateSubnets.map(s => s.id),
      securityGroupId: network.redisSecurityGroup.id,
      stage
    });
    
    // ===== Outputs =====
    return {
      database: {
        endpoint: database.endpoint,
        port: database.port,
        connectionString: database.connectionStringParam
      },
      redis: {
        endpoint: redis.endpoint,
        port: redis.port,
        connectionUrl: redis.redisUrlParam,
        instanceId: redis.instance.id
      },
      network: {
        vpcId: network.vpc.id,
        lambdaSecurityGroupId: network.lambdaSecurityGroup.id
      }
    };
  },
});

