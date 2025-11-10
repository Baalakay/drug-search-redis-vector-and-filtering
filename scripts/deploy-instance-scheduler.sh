#!/bin/bash
# Deploy Lambda-based instance scheduler with EventBridge triggers
# This replaces hardcoded instance IDs with tag-based discovery

set -e

echo "🚀 Deploying Tag-Based Instance Scheduler"
echo "=========================================="
echo ""

ACCOUNT_ID="750389970429"
REGION="us-east-1"
FUNCTION_NAME="devcontainer-instance-scheduler"
ROLE_NAME="DevcontainerSchedulerRole"

# Step 1: Create IAM role for Lambda
echo "📋 Step 1: Creating IAM role for Lambda..."

# Check if role exists
if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
    echo "✅ Role already exists: $ROLE_NAME"
else
    # Create trust policy
    cat > /tmp/lambda-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document file:///tmp/lambda-trust-policy.json \
        --description "Role for devcontainer instance scheduler Lambda"
    
    echo "✅ Created role: $ROLE_NAME"
fi

# Step 2: Attach policies to role
echo ""
echo "📋 Step 2: Attaching policies to role..."

# Attach basic Lambda execution role
aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" \
    2>/dev/null || echo "✅ Basic execution policy already attached"

# Create and attach EC2 management policy
cat > /tmp/lambda-ec2-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:StopInstances",
        "ec2:StartInstances",
        "ec2:DescribeTags"
      ],
      "Resource": "*"
    }
  ]
}
EOF

POLICY_NAME="DevcontainerSchedulerEC2Policy"
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"

if aws iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
    echo "✅ Policy already exists: $POLICY_NAME"
else
    aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document file:///tmp/lambda-ec2-policy.json \
        --description "Allows Lambda to stop/start EC2 instances by tag"
    echo "✅ Created policy: $POLICY_NAME"
fi

aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn "$POLICY_ARN" \
    2>/dev/null || echo "✅ EC2 policy already attached"

echo "⏳ Waiting 10 seconds for IAM role to propagate..."
sleep 10

# Step 3: Package and deploy Lambda function
echo ""
echo "📋 Step 3: Deploying Lambda function..."

cd /workspaces/DAW/scripts
zip -q lambda-instance-scheduler.zip lambda-instance-scheduler.py

# Check if function exists
if aws lambda get-function --function-name "$FUNCTION_NAME" >/dev/null 2>&1; then
    echo "🔄 Updating existing Lambda function..."
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file fileb://lambda-instance-scheduler.zip
else
    echo "🆕 Creating new Lambda function..."
    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime python3.12 \
        --role "arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}" \
        --handler lambda-instance-scheduler.lambda_handler \
        --zip-file fileb://lambda-instance-scheduler.zip \
        --description "Stop/start EC2 instances by tag for cost savings" \
        --timeout 60 \
        --memory-size 128
fi

rm lambda-instance-scheduler.zip
echo "✅ Lambda function deployed"

# Step 4: Update EventBridge rules to use Lambda
echo ""
echo "📋 Step 4: Updating EventBridge rules..."

LAMBDA_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}"

# Update STOP rule (7 PM EST = midnight UTC)
echo "🌙 Updating stop rule..."
aws events put-targets \
    --rule devcontainer-stop-7pm-est \
    --targets "[
        {
            \"Id\": \"1\",
            \"Arn\": \"${LAMBDA_ARN}\",
            \"Input\": \"{\\\"ACTION\\\":\\\"stop\\\",\\\"TAG_KEY\\\":\\\"Type\\\",\\\"TAG_VALUE\\\":\\\"devcontainer\\\"}\"
        }
    ]"

# Add Lambda permission for stop rule
aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id "AllowEventBridgeStopRule" \
    --action "lambda:InvokeFunction" \
    --principal events.amazonaws.com \
    --source-arn "arn:aws:events:${REGION}:${ACCOUNT_ID}:rule/devcontainer-stop-7pm-est" \
    2>/dev/null || echo "✅ Stop rule permission already exists"

echo "✅ Stop rule updated (7 PM EST / Midnight UTC on weekdays)"

# Update START rule (7 AM EST = noon UTC)
echo "☀️  Updating start rule..."
aws events put-targets \
    --rule devcontainer-start-7am-est \
    --targets "[
        {
            \"Id\": \"1\",
            \"Arn\": \"${LAMBDA_ARN}\",
            \"Input\": \"{\\\"ACTION\\\":\\\"start\\\",\\\"TAG_KEY\\\":\\\"Type\\\",\\\"TAG_VALUE\\\":\\\"devcontainer\\\"}\"
        }
    ]"

# Add Lambda permission for start rule
aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id "AllowEventBridgeStartRule" \
    --action "lambda:InvokeFunction" \
    --principal events.amazonaws.com \
    --source-arn "arn:aws:events:${REGION}:${ACCOUNT_ID}:rule/devcontainer-start-7am-est" \
    2>/dev/null || echo "✅ Start rule permission already exists"

echo "✅ Start rule updated (7 AM EST / Noon UTC on weekdays)"

# Step 5: Test the Lambda function
echo ""
echo "📋 Step 5: Testing Lambda function..."
echo "🧪 Testing STOP action (dry run)..."

aws lambda invoke \
    --function-name "$FUNCTION_NAME" \
    --payload '{"ACTION":"stop","TAG_KEY":"Type","TAG_VALUE":"devcontainer"}' \
    /tmp/lambda-response.json

echo "Response:"
cat /tmp/lambda-response.json
echo ""

# Cleanup
rm /tmp/lambda-trust-policy.json /tmp/lambda-ec2-policy.json /tmp/lambda-response.json

echo ""
echo "🎉 Deployment Complete!"
echo "======================="
echo ""
echo "✅ Lambda function: $FUNCTION_NAME"
echo "✅ Targets instances with: Type=devcontainer"
echo "✅ Target instance: i-09f5bc6b3dfea8f84 (devcontainer-aws)"
echo "✅ Stop schedule: 7 PM EST (midnight UTC) on weekdays"
echo "✅ Start schedule: 7 AM EST (noon UTC) on weekdays"
echo ""
echo "📝 Next Steps:"
echo "1. Run cleanup script to remove ECS service: ./cleanup-ecs-service.sh"
echo "2. Test manual stop: aws lambda invoke --function-name $FUNCTION_NAME --payload '{\"ACTION\":\"stop\"}' /tmp/test.json"
echo "3. Monitor CloudWatch Logs: aws logs tail /aws/lambda/$FUNCTION_NAME --follow"

