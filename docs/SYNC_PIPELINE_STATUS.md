# Data Sync Pipeline Deployment Status

## Summary
Phase 4 (Data Sync Pipeline) has been manually deployed due to an SST deployment issue.

## What Was Deployed

### 1. IAM Role ✅
- **Name**: `DAW-DrugSync-Role-dev`
- **ARN**: `arn:aws:iam::750389970429:role/DAW-DrugSync-Role-dev`
- **Policies**:
  - AWS Lambda VPC Access Execution Role (managed policy)
  - Bedrock permissions for embedding generation
  - Secrets Manager permissions for DB credentials
  - CloudWatch Logs permissions
  - CloudWatch Metrics permissions

### 2. Lambda Function ✅
- **Name**: `DAW-DrugSync-dev`
- **ARN**: `arn:aws:lambda:us-east-1:750389970429:function:DAW-DrugSync-dev`
- **Runtime**: Python 3.12
- **Memory**: 1024 MB
- **Timeout**: 900 seconds (15 minutes)
- **VPC**: Deployed in DAW private subnets
- **Environment Variables**:
  ```
  DB_HOST: daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com
  DB_PORT: 3306
  DB_NAME: fdb
  DB_SECRET_ARN: arn:aws:secretsmanager:us-east-1:750389970429:secret:DAW-DB-Password-dev-Tl7ecK
  REDIS_HOST: 10.0.11.245
  REDIS_PORT: 6379
  BATCH_SIZE: 100
  MAX_DRUGS: 0 (all drugs)
  ENABLE_QUANTIZATION: true
  EMBEDDING_MODEL: titan
  ```
- **Status**: Pending (VPC Lambda initialization in progress)

### 3. EventBridge Schedule ✅
- **Rule Name**: `DAW-DrugSync-Schedule-dev`
- **Schedule**: `cron(0 2 * * ? *)` (Daily at 2 AM UTC)
- **State**: ENABLED
- **Target**: Lambda function `DAW-DrugSync-dev`
- **Permissions**: Lambda invoke permission granted to EventBridge

### 4. CloudWatch Resources ✅
- **Log Group**: `/aws/lambda/DAW-DrugSync-dev` (auto-created)
- **Alarms**: Created by SST (DAW-DrugSync-FailureAlarm, DAW-DrugSync-ErrorAlarm)

## SST Deployment Issue

### Problem
SST deployment encountered a "RangeError: Invalid string length" error during the final stage after successfully updating all infrastructure resources (Aurora, Redis, network). This appears to be a Pulumi/SST internal error, not related to our infrastructure code.

### Workaround
Lambda function was manually created using AWS CLI with the correct:
- IAM role (created by SST)
- VPC configuration
- Environment variables
- Event source (EventBridge schedule created by SST)

## Next Steps

1. **Wait for Lambda Initialization**: VPC-attached Lambdas take 2-3 minutes to initialize
2. **Test Lambda Function**: Manually invoke with small batch (10 drugs)
3. **Verify End-to-End**: Check Aurora → Redis data sync
4. **Monitor**: Check CloudWatch Logs for errors

## Testing Commands

```bash
# Check Lambda status
aws lambda get-function \
  --function-name DAW-DrugSync-dev \
  --region us-east-1 \
  --query 'Configuration.State'

# Test Lambda function (once Active)
aws lambda invoke \
  --function-name DAW-DrugSync-dev \
  --cli-binary-format raw-in-base64-out \
  --payload '{"batch_size": 10, "max_drugs": 10}' \
  --region us-east-1 \
  /tmp/lambda_response.json

# Check CloudWatch Logs
aws logs tail /aws/lambda/DAW-DrugSync-dev --follow --region us-east-1
```

## Known Limitations

1. **Missing Dependencies**: Lambda package does not include `mysql-connector-python` or `redis` libraries
   - **Impact**: Lambda will fail on first invocation
   - **Fix**: Need to create Lambda layer with dependencies or use Docker-based deployment

2. **SST State Mismatch**: Lambda was created manually, not tracked by SST
   - **Impact**: Future SST deployments may try to create it again
   - **Fix**: Either remove from `sst.config.ts` or manually import into SST state

## Resolution Plan

1. Create Lambda layer with Python dependencies (`mysql-connector-python`, `redis`, `boto3`)
2. Update Lambda function to use the layer
3. Test end-to-end sync
4. Update SST configuration to either:
   - Skip sync infrastructure deployment, or
   - Fix the "Invalid string length" error (may require SST/Pulumi upgrade)

