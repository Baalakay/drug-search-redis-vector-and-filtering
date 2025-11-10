#!/bin/bash
#
# Create Indexes on FDB Tables
#
# This script creates performance indexes on the loaded FDB data.
# Run this after load-fdb-data.sh completes successfully.
#
# Usage: ./scripts/create-indexes.sh [stage]
# Example: ./scripts/create-indexes.sh dev
#

set -e  # Exit on error

STAGE=${1:-dev}
REGION="us-east-1"

echo "========================================"
echo "Creating Indexes on Aurora (${STAGE})"
echo "========================================"
echo ""

# Check if psql is available
if ! command -v psql &> /dev/null; then
    echo "❌ Error: psql not found. Please install PostgreSQL client first."
    exit 1
fi

# Check if SQL file exists
if [ ! -f "scripts/create-indexes.sql" ]; then
    echo "❌ Error: Index SQL file not found at scripts/create-indexes.sql"
    exit 1
fi

echo "📡 Retrieving database connection string..."
CONNECTION_STRING=$(aws ssm get-parameter \
    --name "/daw/${STAGE}/database/connection-string" \
    --with-decryption \
    --region ${REGION} \
    --query 'Parameter.Value' \
    --output text 2>&1)

if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to retrieve connection string."
    exit 1
fi

echo "✅ Connection string retrieved"
echo ""

# Test database connection
echo "🔌 Testing database connection..."
if ! psql "${CONNECTION_STRING}" -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to database."
    exit 1
fi

echo "✅ Database connection successful"
echo ""

# Create indexes
echo "🔨 Creating indexes (this may take 2-5 minutes)..."
echo ""

START_TIME=$(date +%s)

if psql "${CONNECTION_STRING}" \
    --file="scripts/create-indexes.sql" \
    2>&1 | tee /tmp/create-indexes-${STAGE}.log; then
    
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    MINUTES=$((DURATION / 60))
    SECONDS=$((DURATION % 60))
    
    echo ""
    echo "✅ Indexes created successfully!"
    echo "   Duration: ${MINUTES}m ${SECONDS}s"
    echo ""
else
    echo ""
    echo "❌ Error: Failed to create indexes."
    echo "   Check the log: /tmp/create-indexes-${STAGE}.log"
    exit 1
fi

echo "========================================"
echo "✅ Index Creation Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Test queries: psql \"${CONNECTION_STRING}\""
echo "  2. Deploy sync Lambda to populate Redis"
echo ""

