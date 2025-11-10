#!/bin/bash
#
# Verify DAW Infrastructure Deployment
#
# This script checks that all infrastructure components are deployed
# and accessible.
#
# Usage: ./scripts/verify-deployment.sh [stage]
# Example: ./scripts/verify-deployment.sh dev
#

set -e

STAGE=${1:-dev}
REGION="us-east-1"

echo "========================================"
echo "Verifying DAW Deployment (${STAGE})"
echo "========================================"
echo ""

# ================================================================
# 1. Check Parameter Store for Connection Strings
# ================================================================

echo "1️⃣  Checking Parameter Store..."
echo ""

echo -n "   📍 Database connection string... "
if aws ssm get-parameter \
    --name "/daw/${STAGE}/database/connection-string" \
    --region ${REGION} \
    --query 'Parameter.Name' \
    --output text &> /dev/null; then
    echo "✅"
else
    echo "❌ Not found"
    echo "      Parameter: /daw/${STAGE}/database/connection-string"
fi

echo -n "   📍 Redis connection URL... "
if aws ssm get-parameter \
    --name "/daw/${STAGE}/redis/url" \
    --region ${REGION} \
    --query 'Parameter.Name' \
    --output text &> /dev/null; then
    echo "✅"
else
    echo "❌ Not found"
    echo "      Parameter: /daw/${STAGE}/redis/url"
fi

echo ""

# ================================================================
# 2. Check Aurora Cluster Status
# ================================================================

echo "2️⃣  Checking Aurora PostgreSQL..."
echo ""

CLUSTER_ID="daw-aurora-${STAGE}"
echo -n "   🗄️  Cluster status... "
CLUSTER_STATUS=$(aws rds describe-db-clusters \
    --db-cluster-identifier ${CLUSTER_ID} \
    --region ${REGION} \
    --query 'DBClusters[0].Status' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "${CLUSTER_STATUS}" == "available" ]; then
    echo "✅ Available"
elif [ "${CLUSTER_STATUS}" == "NOT_FOUND" ]; then
    echo "❌ Cluster not found"
else
    echo "⏳ ${CLUSTER_STATUS} (waiting...)"
fi

if [ "${CLUSTER_STATUS}" == "available" ]; then
    echo -n "   📊 Instance count... "
    INSTANCE_COUNT=$(aws rds describe-db-clusters \
        --db-cluster-identifier ${CLUSTER_ID} \
        --region ${REGION} \
        --query 'DBClusters[0].DBClusterMembers | length(@)' \
        --output text 2>/dev/null || echo "0")
    echo "${INSTANCE_COUNT}"
    
    echo -n "   🔌 Endpoint... "
    ENDPOINT=$(aws rds describe-db-clusters \
        --db-cluster-identifier ${CLUSTER_ID} \
        --region ${REGION} \
        --query 'DBClusters[0].Endpoint' \
        --output text 2>/dev/null)
    echo "${ENDPOINT}"
fi

echo ""

# ================================================================
# 3. Check Redis EC2 Instance
# ================================================================

echo "3️⃣  Checking Redis EC2 Instance..."
echo ""

echo -n "   🔴 Instance status... "
REDIS_INSTANCE=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=DAW-Redis-Server-${STAGE}" "Name=instance-state-name,Values=pending,running" \
    --region ${REGION} \
    --query 'Reservations[0].Instances[0]' \
    --output json 2>/dev/null)

if [ "${REDIS_INSTANCE}" != "null" ] && [ ! -z "${REDIS_INSTANCE}" ]; then
    STATE=$(echo ${REDIS_INSTANCE} | jq -r '.State.Name')
    INSTANCE_ID=$(echo ${REDIS_INSTANCE} | jq -r '.InstanceId')
    INSTANCE_TYPE=$(echo ${REDIS_INSTANCE} | jq -r '.InstanceType')
    PRIVATE_IP=$(echo ${REDIS_INSTANCE} | jq -r '.PrivateIpAddress')
    
    if [ "${STATE}" == "running" ]; then
        echo "✅ Running"
        echo "   🆔 Instance ID: ${INSTANCE_ID}"
        echo "   💻 Instance type: ${INSTANCE_TYPE}"
        echo "   🌐 Private IP: ${PRIVATE_IP}"
        
        echo ""
        echo -n "   🔧 Redis service status... "
        # Note: We can't directly check Redis without SSH/SSM access
        echo "⏳ Check via SSM or CloudWatch logs"
    else
        echo "⏳ ${STATE}"
    fi
else
    echo "❌ Instance not found"
fi

echo ""

# ================================================================
# 4. Check VPC Resources
# ================================================================

echo "4️⃣  Checking VPC Resources..."
echo ""

echo -n "   🌐 VPC... "
VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=tag:Name,Values=DAW-VPC" \
    --region ${REGION} \
    --query 'Vpcs[0].VpcId' \
    --output text 2>/dev/null || echo "null")

if [ "${VPC_ID}" != "null" ] && [ ! -z "${VPC_ID}" ]; then
    echo "✅ ${VPC_ID}"
else
    echo "❌ Not found"
fi

echo -n "   🔒 Security groups... "
SG_COUNT=$(aws ec2 describe-security-groups \
    --filters "Name=tag:Project,Values=DAW" \
    --region ${REGION} \
    --query 'SecurityGroups | length(@)' \
    --output text 2>/dev/null || echo "0")
echo "${SG_COUNT} found"

echo -n "   📡 NAT Gateway... "
NAT_COUNT=$(aws ec2 describe-nat-gateways \
    --filter "Name=tag:Project,Values=DAW" "Name=state,Values=available" \
    --region ${REGION} \
    --query 'NatGateways | length(@)' \
    --output text 2>/dev/null || echo "0")

if [ "${NAT_COUNT}" -gt "0" ]; then
    echo "✅ ${NAT_COUNT} available"
else
    echo "⏳ Not available yet"
fi

echo ""

# ================================================================
# 5. Test Database Connection
# ================================================================

echo "5️⃣  Testing Database Connection..."
echo ""

if command -v psql &> /dev/null && [ "${CLUSTER_STATUS}" == "available" ]; then
    echo -n "   🔌 PostgreSQL connection... "
    
    CONNECTION_STRING=$(aws ssm get-parameter \
        --name "/daw/${STAGE}/database/connection-string" \
        --with-decryption \
        --region ${REGION} \
        --query 'Parameter.Value' \
        --output text 2>/dev/null)
    
    if [ ! -z "${CONNECTION_STRING}" ]; then
        if psql "${CONNECTION_STRING}" -c "SELECT version();" > /dev/null 2>&1; then
            echo "✅ Connected"
            
            echo -n "   📊 Database exists... "
            if psql "${CONNECTION_STRING}" -c "SELECT current_database();" > /dev/null 2>&1; then
                echo "✅ Yes"
            fi
        else
            echo "❌ Cannot connect"
            echo "      (Security group may need your IP whitelist)"
        fi
    else
        echo "⏳ Connection string not available yet"
    fi
else
    if [ ! command -v psql &> /dev/null ]; then
        echo "   ⏭️  psql not installed, skipping connection test"
    else
        echo "   ⏳ Aurora cluster not ready yet"
    fi
fi

echo ""

# ================================================================
# Summary
# ================================================================

echo "========================================"
echo "📋 Deployment Status Summary"
echo "========================================"
echo ""

if [ "${CLUSTER_STATUS}" == "available" ] && [ "${STATE}" == "running" ] && [ "${VPC_ID}" != "null" ]; then
    echo "✅ Infrastructure is READY!"
    echo ""
    echo "Next steps:"
    echo "  1. Load FDB data: ./scripts/load-fdb-data.sh ${STAGE}"
    echo "  2. Create indexes: ./scripts/create-indexes.sh ${STAGE}"
    echo "  3. Verify with: psql \"\$(aws ssm get-parameter --name /daw/${STAGE}/database/connection-string --with-decryption --query Parameter.Value --output text)\""
elif [ "${CLUSTER_STATUS}" == "NOT_FOUND" ] || [ "${VPC_ID}" == "null" ]; then
    echo "❌ Infrastructure NOT deployed"
    echo ""
    echo "Run: npx sst deploy --stage ${STAGE}"
else
    echo "⏳ Infrastructure is DEPLOYING..."
    echo ""
    echo "Current status:"
    echo "  - Aurora: ${CLUSTER_STATUS}"
    echo "  - Redis: ${STATE:-Not started}"
    echo "  - VPC: ${VPC_ID}"
    echo ""
    echo "Wait 5-10 minutes and run this script again."
fi

echo ""

