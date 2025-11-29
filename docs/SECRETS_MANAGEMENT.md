# Secrets Management Guide

This document describes how secrets and sensitive configuration are managed in this project.

## Overview

The project uses a multi-layered approach to secrets management:
1. **AWS Secrets Manager** - For production secrets (passwords, tokens)
2. **AWS Systems Manager Parameter Store** - For non-sensitive configuration
3. **Environment Variables** - For local development
4. **Shared Secrets Utility** - Centralized access pattern

## Architecture

### Production (AWS Lambda)

- **Database credentials**: Stored in AWS Secrets Manager (`${PROJECT_NAME}-DB-Password-${STAGE}`)
- **Redis password**: Stored in AWS Secrets Manager (`${PROJECT_NAME}-Redis-AuthToken-${STAGE}`)
- **Lambda functions**: Retrieve secrets via environment variables (Secret ARNs) or direct Secrets Manager API calls

### Local Development (Scripts)

- **Primary**: Environment variables from `.env.local` file
- **Fallback**: AWS Secrets Manager (for AWS environments)
- **Utility**: `packages/core/src/config/secrets.py` provides unified access

## Usage

### For Lambda Functions

Lambda functions receive secrets via environment variables:

```typescript
// infra/search-api.ts
environment: {
  REDIS_PASSWORD: redisPassword,  // From Parameter Store or Secrets Manager
  DB_SECRET_ARN: database.passwordSecretArn  // Reference to Secrets Manager
}
```

In Python Lambda code:

```python
import boto3
import json

def get_db_credentials():
    """Retrieve database credentials from Secrets Manager"""
    sm = boto3.client('secretsmanager')
    response = sm.get_secret_value(SecretId=os.environ['DB_SECRET_ARN'])
    secret = json.loads(response['SecretString'])
    return {
        'user': secret['username'],
        'password': secret['password']
    }
```

### For Local Scripts

Use the shared secrets utility:

```python
from config.secrets import get_db_credentials, get_redis_config, get_redis_password

# Database
db_creds = get_db_credentials()
conn = mysql.connector.connect(**db_creds)

# Redis
redis_config = get_redis_config()
redis_client = redis.Redis(
    host=redis_config['host'],
    port=redis_config['port'],
    password=redis_config['password']
)

# Or just password
password = get_redis_password()
```

### Environment Variables

Create `.env.local` (already gitignored) for local development:

```bash
# .env.local
PROJECT_NAME=DAW
SST_STAGE=dev
AWS_REGION=us-east-1

# Redis (optional - will use Secrets Manager if not set)
REDIS_HOST=10.0.11.153
REDIS_PORT=6379
REDIS_PASSWORD=your-password-here

# Database (optional - will use Secrets Manager if not set)
DB_HOST=daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com
DB_PORT=3306
DB_NAME=fdb
DB_USER=dawadmin
DB_PASSWORD=your-password-here
```

**Priority Order:**
1. Environment variables (`.env.local`)
2. AWS Secrets Manager (for AWS environments)

## Secrets Utility API

### `get_redis_password() -> Optional[str]`

Retrieves Redis password from:
1. `REDIS_PASSWORD` environment variable
2. AWS Secrets Manager: `${PROJECT_NAME}-Redis-AuthToken-${STAGE}`

Returns password string or `None` if not found.

### `get_db_credentials() -> Dict[str, Any]`

Retrieves database credentials from:
1. `DB_HOST`, `DB_USER`, `DB_PASSWORD` environment variables
2. AWS Secrets Manager: `${PROJECT_NAME}-DB-Password-${STAGE}`

Returns dictionary with keys: `host`, `user`, `password`, `database`, `port`

Raises exception if credentials cannot be retrieved.

### `get_redis_config() -> Dict[str, Any]`

Returns complete Redis configuration:
- `host`: From `REDIS_HOST` env var or default
- `port`: From `REDIS_PORT` env var or 6379
- `password`: From `get_redis_password()`

### `get_secret_from_manager(secret_name: str, key: Optional[str] = None) -> Optional[str]`

Generic function to retrieve any secret from AWS Secrets Manager.

## Secret Storage Locations

### AWS Secrets Manager

| Secret Name | Format | Contains |
|------------|--------|----------|
| `${PROJECT_NAME}-DB-Password-${STAGE}` | JSON | `{"username": "dawadmin", "password": "..."}` |
| `${PROJECT_NAME}-Redis-AuthToken-${STAGE}` | String or JSON | Redis password/auth token |

### AWS Parameter Store

| Parameter Path | Type | Contains |
|---------------|------|----------|
| `/${PROJECT_NAME}/${STAGE}/database/connection-string` | SecureString | Full MySQL connection string |
| `/${PROJECT_NAME}/${STAGE}/redis/url` | String | Redis connection URL |
| `/${PROJECT_NAME}/${STAGE}/redis/host` | String | Redis host IP |

## Migration Guide

### Updating Scripts

**Before:**
```python
password = 'DAW-Redis-SecureAuth-2025'
redis_client = redis.Redis(host='10.0.11.153', password=password)
```

**After:**
```python
from config.secrets import get_redis_config

redis_config = get_redis_config()
redis_client = redis.Redis(**redis_config)
```

### Updating Infrastructure

**Before:**
```typescript
const redisPassword = process.env.REDIS_PASSWORD || "hardcoded-password";
```

**After:**
```typescript
// Prefer environment variable, mark fallback as secret
const redisPassword = process.env.REDIS_PASSWORD || 
  pulumi.secret(`${$app.name}-Redis-SecureAuth-2025`);
```

## Security Best Practices

1. ✅ **Never commit secrets** - `.env.local` is gitignored
2. ✅ **Use Secrets Manager for production** - All production secrets in AWS Secrets Manager
3. ✅ **Use Parameter Store for non-sensitive config** - Hosts, ports, etc.
4. ✅ **Mark secrets in infrastructure code** - Use `pulumi.secret()` for fallback values
5. ✅ **Rotate secrets regularly** - Update Secrets Manager, not code
6. ✅ **Use IAM roles** - Lambda functions use IAM roles, not access keys
7. ✅ **Limit secret access** - IAM policies restrict who can read secrets

## Troubleshooting

### Script can't find secrets

1. Check `.env.local` exists and has correct values
2. Verify AWS credentials are configured (`aws configure` or environment variables)
3. Check secret name matches: `${PROJECT_NAME}-*-${STAGE}`
4. Verify IAM permissions for Secrets Manager access

### Lambda can't access secrets

1. Check Lambda execution role has `secretsmanager:GetSecretValue` permission
2. Verify secret ARN is correct in environment variables
3. Check VPC configuration (Lambda needs VPC endpoint or NAT gateway for Secrets Manager)

### Environment variable not working

1. Ensure `.env.local` is in project root
2. Restart script/process after changing `.env.local`
3. Check variable names match exactly (case-sensitive)

## Related Files

- `packages/core/src/config/secrets.py` - Secrets utility implementation
- `.env.local.example` - Template for local environment variables
- `infra/database.ts` - Database secret creation
- `infra/redis-ec2.ts` - Redis secret creation
- `infra/search-api.ts` - Lambda environment variable configuration

