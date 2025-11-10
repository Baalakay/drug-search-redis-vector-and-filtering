#!/bin/bash
# Clean up the failing ECS service that's not being used

set -e

echo "🧹 Cleaning Up ECS Service"
echo "=========================="
echo ""

CLUSTER_NAME="devcontainer-cluster"
SERVICE_NAME="devcontainer-service"

# Step 1: Check current service status
echo "📋 Step 1: Checking service status..."
SERVICE_STATUS=$(aws ecs describe-services \
    --cluster "$CLUSTER_NAME" \
    --services "$SERVICE_NAME" \
    --query 'services[0].status' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$SERVICE_STATUS" = "NOT_FOUND" ] || [ -z "$SERVICE_STATUS" ]; then
    echo "✅ Service already deleted or doesn't exist"
    exit 0
fi

echo "Current status: $SERVICE_STATUS"
echo ""

# Step 2: Scale service to 0
echo "📋 Step 2: Scaling service to 0..."
aws ecs update-service \
    --cluster "$CLUSTER_NAME" \
    --service "$SERVICE_NAME" \
    --desired-count 0 \
    --query 'service.[serviceName,desiredCount,runningCount]' \
    --output table

echo "✅ Service scaled to 0"
echo "⏳ Waiting 30 seconds for tasks to stop..."
sleep 30

# Step 3: Delete the service
echo ""
echo "📋 Step 3: Deleting service..."
aws ecs delete-service \
    --cluster "$CLUSTER_NAME" \
    --service "$SERVICE_NAME" \
    --force \
    --query 'service.[serviceName,status]' \
    --output table

echo "✅ Service deleted"
echo ""

# Step 4: Optionally remove capacity provider (keeps cluster)
read -p "Do you want to remove the capacity provider from the cluster? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📋 Removing capacity provider association..."
    aws ecs put-cluster-capacity-providers \
        --cluster "$CLUSTER_NAME" \
        --capacity-providers [] \
        --default-capacity-provider-strategy []
    echo "✅ Capacity provider removed from cluster"
fi

echo ""
echo "🎉 Cleanup Complete!"
echo "==================="
echo ""
echo "✅ ECS service deleted (no more failed tasks)"
echo "✅ ASG still exists with its instance (i-00fad2709b0313160)"
echo "✅ Your devcontainer instance is separate: i-09f5bc6b3dfea8f84"
echo ""
echo "📝 Your instance (i-09f5bc6b3dfea8f84) will be managed by:"
echo "   - Lambda function: devcontainer-instance-scheduler"
echo "   - Tag: Type=devcontainer"
echo "   - Stop: 7 PM EST weekdays"
echo "   - Start: 7 AM EST weekdays"
echo ""
echo "💡 Optional: You can also delete the ASG if you don't need auto-recovery:"
echo "   aws autoscaling delete-auto-scaling-group --auto-scaling-group-name devcontainer-asg --force-delete"

