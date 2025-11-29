"""
Secrets Management Utility
Centralized functions for retrieving secrets from environment variables or AWS Secrets Manager

Usage:
    from config.secrets import get_redis_password, get_db_credentials
    
    # Redis
    password = get_redis_password()
    redis_client = redis.Redis(host=os.environ.get('REDIS_HOST'), password=password)
    
    # Database
    db_creds = get_db_credentials()
    conn = mysql.connector.connect(**db_creds)
"""

import os
import json
import boto3
from typing import Optional, Dict, Any
from functools import lru_cache


@lru_cache(maxsize=1)
def _get_secrets_client():
    """Get cached Secrets Manager client"""
    region = os.environ.get('AWS_REGION', 'us-east-1')
    return boto3.client('secretsmanager', region_name=region)


def get_project_name() -> str:
    """Get project name from environment or default"""
    return os.environ.get('PROJECT_NAME', 'DAW')


def get_stage() -> str:
    """Get stage from environment or default"""
    return os.environ.get('SST_STAGE', 'dev')


def get_redis_password() -> Optional[str]:
    """
    Get Redis password from environment variable or AWS Secrets Manager.
    
    Priority:
    1. REDIS_PASSWORD environment variable (for local dev)
    2. AWS Secrets Manager secret: ${PROJECT_NAME}-Redis-AuthToken-${STAGE}
    
    Returns:
        Redis password string, or None if not found
    """
    # 1. Check environment variable first (for local dev)
    password = os.environ.get('REDIS_PASSWORD')
    if password:
        return password
    
    # 2. Fall back to Secrets Manager (for AWS environments)
    try:
        sm = _get_secrets_client()
        project_name = get_project_name()
        stage = get_stage()
        secret_name = f"{project_name}-Redis-AuthToken-{stage}"
        
        response = sm.get_secret_value(SecretId=secret_name)
        secret_string = response['SecretString']
        
        # Try parsing as JSON first (if stored as {"password": "..."} or {"authToken": "..."})
        try:
            secret_dict = json.loads(secret_string)
            return secret_dict.get('password') or secret_dict.get('authToken') or secret_string
        except (json.JSONDecodeError, TypeError):
            # If not JSON, return as-is
            return secret_string
    except Exception as e:
        print(f"⚠️ Could not retrieve Redis password from Secrets Manager: {e}")
        print(f"   Tried secret name: {project_name}-Redis-AuthToken-{stage}")
        return None


def get_db_credentials() -> Dict[str, Any]:
    """
    Get database credentials from environment variables or AWS Secrets Manager.
    
    Priority:
    1. DB_HOST, DB_USER, DB_PASSWORD environment variables (for local dev)
    2. AWS Secrets Manager secret: ${PROJECT_NAME}-DB-Password-${STAGE}
    
    Returns:
        Dictionary with keys: host, user, password, database, port
        
    Raises:
        Exception: If credentials cannot be retrieved
    """
    project_name = get_project_name()
    stage = get_stage()
    
    # 1. Check if all required env vars are set (for local dev)
    db_host = os.environ.get('DB_HOST')
    db_user = os.environ.get('DB_USER')
    db_password = os.environ.get('DB_PASSWORD')
    
    if db_host and db_user and db_password:
        return {
            'host': db_host,
            'user': db_user,
            'password': db_password,
            'database': os.environ.get('DB_NAME', 'fdb'),
            'port': int(os.environ.get('DB_PORT', '3306'))
        }
    
    # 2. Fall back to Secrets Manager
    try:
        sm = _get_secrets_client()
        secret_name = f"{project_name}-DB-Password-{stage}"
        
        response = sm.get_secret_value(SecretId=secret_name)
        secret_dict = json.loads(response['SecretString'])
        
        # Default host if not in env (for dev stage)
        default_host = os.environ.get('DB_HOST')
        if not default_host and stage == 'dev':
            default_host = 'daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com'
        
        return {
            'host': os.environ.get('DB_HOST', default_host or ''),
            'user': secret_dict.get('username', 'dawadmin'),
            'password': secret_dict.get('password', ''),
            'database': os.environ.get('DB_NAME', 'fdb'),
            'port': int(os.environ.get('DB_PORT', '3306'))
        }
    except Exception as e:
        raise Exception(
            f"Could not retrieve DB credentials from Secrets Manager: {e}\n"
            f"Tried secret name: {project_name}-DB-Password-{stage}\n"
            f"Set DB_HOST, DB_USER, DB_PASSWORD environment variables for local development."
        )


def get_redis_config() -> Dict[str, Any]:
    """
    Get complete Redis configuration.
    
    Returns:
        Dictionary with keys: host, port, password
    """
    return {
        'host': os.environ.get('REDIS_HOST', '10.0.11.153'),
        'port': int(os.environ.get('REDIS_PORT', '6379')),
        'password': get_redis_password()
    }


def get_secret_from_manager(secret_name: str, key: Optional[str] = None) -> Optional[str]:
    """
    Generic function to retrieve a secret from AWS Secrets Manager.
    
    Args:
        secret_name: Name of the secret in Secrets Manager
        key: Optional key to extract from JSON secret. If None, returns raw secret string.
    
    Returns:
        Secret value (string or dict), or None if not found
    """
    try:
        sm = _get_secrets_client()
        response = sm.get_secret_value(SecretId=secret_name)
        secret_string = response['SecretString']
        
        if key:
            try:
                secret_dict = json.loads(secret_string)
                return secret_dict.get(key)
            except (json.JSONDecodeError, TypeError):
                return None
        
        # Try parsing as JSON, return dict if successful, else return string
        try:
            return json.loads(secret_string)
        except (json.JSONDecodeError, TypeError):
            return secret_string
    except Exception as e:
        print(f"⚠️ Could not retrieve secret '{secret_name}': {e}")
        return None

