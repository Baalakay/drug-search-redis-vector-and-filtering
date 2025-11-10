#!/bin/bash
set -e

echo "=== Starting FDB Data Load ==="
echo "Time: $(date)"
echo

# Get DB credentials from Secrets Manager
DB_SECRET=$(aws secretsmanager get-secret-value --secret-id DAW-DB-Password-dev --region us-east-1 --query SecretString --output text)
DB_USER=$(echo $DB_SECRET | sed -n 's/.*"username":"\([^"]*\)".*/\1/p')
DB_PASS=$(echo $DB_SECRET | sed -n 's/.*"password":"\([^"]*\)".*/\1/p')

# Aurora MySQL connection details
DB_HOST="daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com"
DB_PORT="3306"
DB_NAME="daw"

echo "Testing connection to $DB_HOST..."
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "SELECT VERSION();" | head -3
echo

echo "Filtering SQL file to remove problematic SET commands..."
grep -v "@@SESSION.SQL_LOG_BIN" /tmp/fdb-tables.sql | grep -v "@@GLOBAL.GTID_PURGED" > /tmp/fdb-filtered.sql
ls -lh /tmp/fdb-filtered.sql
echo

echo "Starting SQL import (this will take several minutes)..."
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" < /tmp/fdb-filtered.sql 2>&1 | tail -30

echo
echo "=== Load Complete at $(date) ==="
echo

echo "Tables created:"
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "SELECT COUNT(*) as total_tables FROM information_schema.tables WHERE table_schema='$DB_NAME';"

echo
echo "Top 10 largest tables:"
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "SELECT table_name, ROUND(((data_length + index_length) / 1024 / 1024), 2) AS size_mb FROM information_schema.tables WHERE table_schema='$DB_NAME' ORDER BY (data_length + index_length) DESC LIMIT 10;"

