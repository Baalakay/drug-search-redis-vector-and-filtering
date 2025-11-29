"""
DAW Configuration Module
Centralized configuration for Lambda functions and Fargate jobs
"""

from .practice_config import (
    PracticeConfig,
    get_default_config,
    get_practice_config_for_clinic,
    PriorityLevel,
    TimeThresholds,
    ProximityThresholds,
    CandidateLimits,
    AttendanceThreshold,
    StrategyThresholds,
)
from .llm_config import (
    MODEL_CONFIG,
    DEFAULT_MODEL,
    validate_model_id,
    get_llm_config,
    get_model_config,
    get_available_models
)
from .secrets import (
    get_redis_password,
    get_db_credentials,
    get_redis_config,
    get_secret_from_manager,
    get_project_name,
    get_stage,
)

__all__ = [
    # Practice config
    "PracticeConfig",
    "get_default_config",
    "get_practice_config_for_clinic",
    "PriorityLevel",
    "TimeThresholds",
    "ProximityThresholds",
    "CandidateLimits",
    "AttendanceThreshold",
    "StrategyThresholds",
    # LLM config
    "MODEL_CONFIG",
    "DEFAULT_MODEL",
    "validate_model_id",
    "get_llm_config",
    "get_model_config",
    "get_available_models",
    # Secrets management
    "get_redis_password",
    "get_db_credentials",
    "get_redis_config",
    "get_secret_from_manager",
    "get_project_name",
    "get_stage",
]
