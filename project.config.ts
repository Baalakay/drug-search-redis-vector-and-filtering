/**
 * DAW Project Configuration
 * 
 * Centralized configuration for stage-specific settings
 */

export const projectConfig = {
  projectName: "DAW",
  description: "DAW E-Prescribing Platform - Drug Search System",
  
  naming: {
    prefix: "DAW",  // All resources start or end with "DAW"
  },
  
  stages: {
    dev: {
      protect: false,
      removal: "remove" as const,
      account: process.env.AWS_ACCOUNT_ID_DEV || "750389970429",  // Actual AWS account
      region: "us-east-1",
    },
    staging: {
      protect: false,
      removal: "remove" as const,
      account: process.env.AWS_ACCOUNT_ID_STAGING || "234567890123",
      region: "us-east-1",
    },
    prod: {
      protect: true,
      removal: "retain" as const,
      account: process.env.AWS_ACCOUNT_ID_PROD || "345678901234",
      region: "us-east-1",
    },
  },
} as const;

export function getStageConfig(stage: string) {
  const config = projectConfig.stages[stage as keyof typeof projectConfig.stages];
  if (!config) {
    throw new Error(`Invalid stage: ${stage}. Must be one of: ${Object.keys(projectConfig.stages).join(", ")}`);
  }
  return config;
}

export function getAccountConfig(stage: string) {
  return getStageConfig(stage).account;
}

