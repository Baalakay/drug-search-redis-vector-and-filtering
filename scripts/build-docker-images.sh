#!/bin/bash

#
# Build and Push Docker Images for Fargate Jobs
# This script is called as part of the SST deployment workflow
#

set -e  # Exit on error

# Configuration
STAGE="${1:-dev}"
REGION="ca-central-1"
PROFILE="DAW"
ACCOUNT_ID="491668389079"

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Docker Image Build & Push for Stage: ${STAGE}${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

# Get project root (two levels up from scripts/)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# ECR Login
echo -e "\n${GREEN}🔐 Logging into ECR...${NC}"
aws ecr get-login-password --profile ${PROFILE} --region ${REGION} | \
  docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com

# Job #1: Aggregate Metrics
REPO_NAME_1="DAW-aggregate-metrics-v2-${STAGE}"
echo -e "\n${GREEN}🐳 Building ${REPO_NAME_1}...${NC}"
docker build \
  --platform linux/amd64 \
  -f packages/jobs/aggregate-metrics/Dockerfile \
  -t ${REPO_NAME_1}:latest \
  .

echo -e "${GREEN}📤 Pushing ${REPO_NAME_1}:latest...${NC}"
docker tag ${REPO_NAME_1}:latest ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME_1}:latest
docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME_1}:latest

# Job #2: Priority Analysis
REPO_NAME_2="DAW-priority-analysis-v2-${STAGE}"
echo -e "\n${GREEN}🐳 Building ${REPO_NAME_2}...${NC}"
docker build \
  --platform linux/amd64 \
  -f packages/jobs/priority-analysis/Dockerfile \
  -t ${REPO_NAME_2}:latest \
  .

echo -e "${GREEN}📤 Pushing ${REPO_NAME_2}:latest...${NC}"
docker tag ${REPO_NAME_2}:latest ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME_2}:latest
docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME_2}:latest

echo -e "\n${GREEN}✅ Docker images built and pushed successfully!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Next steps:${NC}"
echo -e "  1. Run: ${BLUE}npx sst deploy --stage ${STAGE}${NC}"
echo -e "  2. Trigger jobs via AWS CLI or EventBridge"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"

