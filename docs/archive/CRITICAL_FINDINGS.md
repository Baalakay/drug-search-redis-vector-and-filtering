# Critical Findings from Documentation Review

## ROOT CAUSE DISCOVERED ✅

After reading both docs fully, I found **THE CRITICAL ERROR**:

### We Were Using The Wrong SST Construct!

**Problem**: We were using raw Pulumi `aws.lambda.Function` instead of SST's native `sst.aws.Function`

**Evidence from SST_LAMBDA_MIGRATION_COMPLETE_GUIDE.md line 1396**:
```typescript
const dataProcessor = new sst.aws.Function("DataProcessor", {
```

**Why This Caused Silent Failures**:
- Raw Pulumi Lambda functions don't integrate properly with SST's packaging system
- SST couldn't handle the Python dependencies 
- Promise rejections were caught and swallowed by Pulumi's error handlers
- Resources like IAM role, EventBridge, CloudWatch alarms were created, but the Lambda function itself failed silently

## Additional Issues Found

1. **VPC Property Renamed**: SST changed `vpc.subnets` → `vpc.privateSubnets`  
   - Fixed in code

2. **UV Package Error**: `daw-scripts` package in `packages/scripts` missing proper hatchling configuration
   - This is a workspace package, not related to Lambda
   - Could be excluded from UV workspace if not needed

3. **Aurora State Issue**: Using `.get()` causes "already exists" error, but using `new` with `protect: true` should work

## Current Status

✅ Switched to `sst.aws.Function`  
✅ Fixed VPC property name  
✅ Node v24.5.0 set as default  
⏸️ Need to handle Aurora state conflict  
⏸️ Need to fix or exclude `daw-scripts` package  

## Next Actions

1. Import Aurora into Pulumi state OR temporarily exclude sync from deployment
2. Fix `packages/scripts/pyproject.toml` or exclude from workspace
3. Deploy again with SST native Function construct
4. Test Lambda creation

---

**Key Lesson**: ALWAYS use SST's native constructs (`sst.aws.Function`) instead of raw Pulumi AWS resources for Lambda functions. The guides explicitly show this pattern throughout.

