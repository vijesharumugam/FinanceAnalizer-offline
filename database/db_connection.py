"""MySQL connection utilities for the finance analyzer."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import mysql.connector
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from config import get_settings


class DatabaseManager:
    """Centralized database bootstrapper and engine factory."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None

    def create_database_if_not_exists(self) -> None:
        """Create the target database before SQLAlchemy connects to it."""

        cursor = None
        connection = mysql.connector.connect(
            host=self.settings.db_host,
            port=self.settings.db_port,
            user=self.settings.db_user,
            password=self.settings.db_password,
        )
        try:
            cursor = connection.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.settings.db_name}")
            connection.commit()
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def _split_sql_statements(self, sql_script: str) -> list[str]:
        """Split a schema file into executable statements."""

        statements: list[str] = []
        current_lines: list[str] = []

        for raw_line in sql_script.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("--"):
                continue
            current_lines.append(raw_line)
            if line.endswith(";"):
                statement = "\n".join(current_lines).strip().rstrip(";").strip()
                current_lines = []
                if not statement:
                    continue
                upper_statement = statement.upper()
                if upper_statement.startswith("CREATE DATABASE ") or upper_statement.startswith("USE "):
                    continue
                statements.append(statement)

        trailing_statement = "\n".join(current_lines).strip()
        if trailing_statement:
            upper_statement = trailing_statement.upper()
            if not (upper_statement.startswith("CREATE DATABASE ") or upper_statement.startswith("USE ")):
                statements.append(trailing_statement)

        return statements

    def initialize_schema(self, schema_path: Optional[Path] = None) -> None:
        """Apply the MySQL schema script in an idempotent way."""

        self.create_database_if_not_exists()
        schema_file = schema_path or Path(__file__).with_name("schema.sql")
        sql_script = schema_file.read_text(encoding="utf-8")

        cursor = None
        connection = mysql.connector.connect(
            host=self.settings.db_host,
            port=self.settings.db_port,
            user=self.settings.db_user,
            password=self.settings.db_password,
            database=self.settings.db_name,
        )
        try:
            cursor = connection.cursor()
            for statement in self._split_sql_statements(sql_script):
                cursor.execute(statement)
            connection.commit()
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def get_engine(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(
                self.settings.sqlalchemy_url,
                pool_pre_ping=True,
                pool_recycle=3600,
                future=True,
            )
        return self._engine

    def get_session_factory(self) -> sessionmaker:
        if self._session_factory is None:
            self._session_factory = sessionmaker(bind=self.get_engine(), autoflush=False, autocommit=False)
        return self._session_factory

    def test_connection(self) -> bool:
        engine = self.get_engine()
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        return True


_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
