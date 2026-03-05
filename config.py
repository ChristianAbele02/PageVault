from __future__ import annotations

import os
from pathlib import Path


class BaseConfig:
    DATABASE = os.getenv("PAGEVAULT_DB") or str(Path(__file__).parent / "pagevault.db")
    SECRET_KEY = os.getenv("SECRET_KEY") or "change-me-in-production"
    JSON_SORT_KEYS = False

    # Admin auth defaults. Change PAGEVAULT_ADMIN_PASSWORD in production.
    ADMIN_PASSWORD = os.getenv("PAGEVAULT_ADMIN_PASSWORD") or "1111"
    LOG_FILE = os.getenv("PAGEVAULT_LOG_FILE") or str(Path(__file__).parent / "pagevault.log")


class DevConfig(BaseConfig):
    DEBUG = True


class TestConfig(BaseConfig):
    TESTING = True


class ProdConfig(BaseConfig):
    DEBUG = False


def resolve_config(config_name: str | None):
    mapping = {
        "development": DevConfig,
        "dev": DevConfig,
        "testing": TestConfig,
        "test": TestConfig,
        "production": ProdConfig,
        "prod": ProdConfig,
    }
    return mapping.get((config_name or "").strip().lower(), BaseConfig)
