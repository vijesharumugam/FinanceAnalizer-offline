"""Application configuration and shared constants."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()

APP_NAME = "AI Personal Finance Analyzer"
EXPENSE_CATEGORIES = [
    "Food",
    "Travel",
    "Shopping",
    "Rent",
    "Entertainment",
    "Bills",
    "Health",
    "Education",
    "Others",
]


@dataclass(frozen=True)
class Settings:
    """Environment-driven application settings."""

    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "3306"))
    db_user: str = os.getenv("DB_USER", "root")
    db_password: str = os.getenv("DB_PASSWORD", "")
    db_name: str = os.getenv("DB_NAME", "finance_analyzer")
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    secret_key: str = os.getenv("SECRET_KEY", "change-me")

    @property
    def sqlalchemy_url(self) -> str:
        encoded_password = quote_plus(self.db_password)
        return (
            f"mysql+mysqlconnector://{self.db_user}:{encoded_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def configure_logging() -> logging.Logger:
    """Configure root logging once and return an app logger."""

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger(APP_NAME)
