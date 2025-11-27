#!/bin/bash
# Test the Lambda-based instance scheduler

set -e

FUNCTION_NAME="devcontainer-instance-scheduler"

echo "🧪 Testing Instance Scheduler Lambda"
echo "====================================="
echo ""

echo "📋 Current instance status:"
aws ec2 describe-instances \
    --filters "Name=tag:Type,Values=devcontainer" \
    --query 'Reservations[*].Instances[*].[InstanceId,State.Name,Tags[?Key==`Name`].Value|[0]]' \
    --output table

echo ""
echo "🧪 Test 1: Invoke STOP action (won't stop running instances, just shows what would happen)"
aws lambda invoke \
    --function-name "$FUNCTION_NAME" \
    --payload '{"ACTION":"stop","TAG_KEY":"Type","TAG_VALUE":"devcontainer"}' \
    /tmp/stop-response.json

echo "Stop Response:"
cat /tmp/stop-response.json
echo ""
echo ""

echo "🧪 Test 2: Invoke START action"
aws lambda invoke \
    --function-name "$FUNCTION_NAME" \
    --payload '{"ACTION":"start","TAG_KEY":"Type","TAG_VALUE":"devcontainer"}' \
    /tmp/start-response.json

echo "Start Response:"
cat /tmp/start-response.json
echo ""
echo ""

echo "📋 View recent CloudWatch logs:"
echo "aws logs tail /aws/lambda/$FUNCTION_NAME --follow"
echo ""

echo "📋 Manually stop instance for testing:"
echo "aws ec2 stop-instances --instance-ids i-09f5bc6b3dfea8f84"
echo ""

echo "📋 Manually start instance:"
echo "aws ec2 start-instances --instance-ids i-09f5bc6b3dfea8f84"
echo ""

rm /tmp/stop-response.json /tmp/start-response.json

echo "✅ Tests complete!"

