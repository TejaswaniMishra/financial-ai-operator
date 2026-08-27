import os
from enum import Enum


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


def get_current_environment() -> Environment:
    """Retrieve the current application environment with fallback to development."""
    env_str = os.getenv("APP_ENV", "development").lower()
    try:
        return Environment(env_str)
    except ValueError:
        return Environment.DEVELOPMENT
