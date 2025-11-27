#!/bin/bash
#
# Load FDB Data into Aurora PostgreSQL
#
# This script loads the FDB tables SQL dump into the deployed Aurora database.
# It retrieves connection credentials from AWS Parameter Store (deployed by SST).
#
# Usage: ./scripts/load-fdb-data.sh [stage]
# Example: ./scripts/load-fdb-data.sh dev
#

set -e  # Exit on error

STAGE=${1:-dev}
REGION="us-east-1"

echo "======================================"
echo "Loading FDB Data to Aurora (${STAGE})"
echo "======================================"
echo ""

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo "❌ Error: AWS CLI not found. Please install it first."
    exit 1
fi

# Check if psql is available
if ! command -v psql &> /dev/null; then
    echo "❌ Error: psql not found. Please install PostgreSQL client first."
    echo "   sudo apt-get install postgresql-client"
    exit 1
fi

# Check if SQL file exists
if [ ! -f "database/imports/fdb tables.sql" ]; then
    echo "❌ Error: FDB tables SQL file not found at database/imports/fdb tables.sql"
    exit 1
fi

echo "📡 Retrieving database connection string from Parameter Store..."
CONNECTION_STRING=$(aws ssm get-parameter \
    --name "/daw/${STAGE}/database/connection-string" \
    --with-decryption \
    --region ${REGION} \
    --query 'Parameter.Value' \
    --output text 2>&1)

if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to retrieve connection string from Parameter Store."
    echo "   Make sure the infrastructure is deployed: npx sst deploy --stage ${STAGE}"
    echo ""
    echo "   Parameter name: /daw/${STAGE}/database/connection-string"
    exit 1
fi

echo "✅ Connection string retrieved"
echo ""

# Test database connection
echo "🔌 Testing database connection..."
if ! psql "${CONNECTION_STRING}" -c "SELECT version();" > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to database."
    echo "   Connection string: ${CONNECTION_STRING}"
    echo ""
    echo "   Possible issues:"
    echo "   1. Aurora cluster is still initializing (wait a few minutes)"
    echo "   2. Security group not allowing your IP"
    echo "   3. VPN/network connectivity issues"
    exit 1
fi

echo "✅ Database connection successful"
echo ""

# Get file size for progress indication
FILE_SIZE=$(du -h "database/imports/fdb tables.sql" | cut -f1)
echo "📦 Loading FDB tables SQL dump (${FILE_SIZE})..."
echo "   This may take 5-15 minutes depending on file size..."
echo ""

# Load the SQL file
# Use --single-transaction for atomic load (all or nothing)
# Use --set ON_ERROR_STOP=on to stop on first error
START_TIME=$(date +%s)

if psql "${CONNECTION_STRING}" \
    --single-transaction \
    --set ON_ERROR_STOP=on \
    --file="database/imports/fdb tables.sql" \
    2>&1 | tee /tmp/fdb-load-${STAGE}.log; then
    
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    MINUTES=$((DURATION / 60))
    SECONDS=$((DURATION % 60))
    
    echo ""
    echo "✅ FDB data loaded successfully!"
    echo "   Duration: ${MINUTES}m ${SECONDS}s"
    echo ""
else
    echo ""
    echo "❌ Error: Failed to load FDB data."
    echo "   Check the log file: /tmp/fdb-load-${STAGE}.log"
    exit 1
fi

# Verify data loaded
echo "🔍 Verifying data..."
echo ""

# Check key tables exist and have data
TABLES=("rndc14" "rgcnseq4" "rnp2")
for table in "${TABLES[@]}"; do
    echo -n "   Checking ${table}... "
    
    if ! COUNT=$(psql "${CONNECTION_STRING}" -t -c "SELECT COUNT(*) FROM ${table};" 2>&1); then
        echo "❌ Table not found or error"
        continue
    fi
    
    COUNT=$(echo $COUNT | xargs)  # Trim whitespace
    echo "✅ ${COUNT} rows"
done

echo ""
echo "======================================"
echo "✅ FDB Data Load Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. Create indexes: ./scripts/create-indexes.sh ${STAGE}"
echo "  2. Verify queries: psql \"${CONNECTION_STRING}\""
echo ""

