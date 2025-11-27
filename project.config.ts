/**
 * Project Configuration
 * 
 * Centralized configuration for stage-specific settings
 * 
 * TO CUSTOMIZE FOR YOUR PROJECT:
 * 1. Change projectName to your project name
 * 2. Update description
 * 3. Update AWS account IDs for each stage
 */

export const projectConfig = {
  projectName: process.env.PROJECT_NAME || "DAW",  // Override via PROJECT_NAME env var
  description: process.env.PROJECT_DESCRIPTION || "E-Prescribing Platform - Drug Search System",
  
  naming: {
    prefix: process.env.PROJECT_PREFIX || "DAW",  // Override via PROJECT_PREFIX env var
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

