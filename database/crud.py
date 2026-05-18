"""CRUD operations backed by MySQL."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import text

from database.db_connection import get_database_manager


class FinanceCRUD:
    """SQL-backed data access layer for app operations."""

    def __init__(self) -> None:
        self.engine = get_database_manager().get_engine()

    def _read_dataframe(self, query, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        with self.engine.connect() as connection:
            return pd.read_sql_query(query, connection, params=params)

    def _coerce_numeric_series(self, series: pd.Series) -> pd.Series:
        return pd.to_numeric(series, errors="coerce")

    def _coerce_boolean_series(self, series: pd.Series) -> pd.Series:
        if series.empty:
            return series.astype(bool)
        if pd.api.types.is_bool_dtype(series):
            return series.fillna(False)

        normalized = series.astype(str).str.strip().str.lower().map(
            {
                "1": True,
                "true": True,
                "t": True,
                "yes": True,
                "y": True,
                "0": False,
                "false": False,
                "f": False,
                "no": False,
                "n": False,
                "none": False,
                "nan": False,
            }
        )
        return normalized.fillna(False).astype(bool)

    def create_user(self, full_name: str, email: str, username: str, password_hash: str) -> int:
        query = text(
            """
            INSERT INTO users (full_name, email, username, password_hash)
            VALUES (:full_name, :email, :username, :password_hash)
            """
        )
        with self.engine.begin() as connection:
            result = connection.execute(
                query,
                {
                    "full_name": full_name,
                    "email": email,
                    "username": username,
                    "password_hash": password_hash,
                },
            )
            return int(result.lastrowid)

    def get_user_by_identifier(self, identifier: str) -> Optional[Dict[str, Any]]:
        query = text(
            """
            SELECT *
            FROM users
            WHERE email = :identifier OR username = :identifier
            LIMIT 1
            """
        )
        with self.engine.connect() as connection:
            result = connection.execute(query, {"identifier": identifier.strip().lower()}).mappings().first()
            return dict(result) if result else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        query = text("SELECT * FROM users WHERE id = :user_id LIMIT 1")
        with self.engine.connect() as connection:
            result = connection.execute(query, {"user_id": user_id}).mappings().first()
            return dict(result) if result else None

    def add_expense(self, user_id: int, expense: Dict[str, Any]) -> int:
        query = text(
            """
            INSERT INTO expenses (user_id, txn_date, amount, category, merchant, description, payment_method, source)
            VALUES (:user_id, :txn_date, :amount, :category, :merchant, :description, :payment_method, :source)
            """
        )
        payload = {
            "user_id": user_id,
            "txn_date": expense["txn_date"],
            "amount": float(expense["amount"]),
            "category": expense["category"],
            "merchant": expense.get("merchant", ""),
            "description": expense.get("description", ""),
            "payment_method": expense.get("payment_method", "Unknown"),
            "source": expense.get("source", "manual"),
        }
        with self.engine.begin() as connection:
            result = connection.execute(query, payload)
            return int(result.lastrowid)

    def update_expense(self, expense_id: int, user_id: int, expense: Dict[str, Any]) -> None:
        query = text(
            """
            UPDATE expenses
            SET txn_date = :txn_date,
                amount = :amount,
                category = :category,
                merchant = :merchant,
                description = :description,
                payment_method = :payment_method,
                source = :source
            WHERE id = :expense_id AND user_id = :user_id
            """
        )
        payload = {
            "expense_id": expense_id,
            "user_id": user_id,
            "txn_date": expense["txn_date"],
            "amount": float(expense["amount"]),
            "category": expense["category"],
            "merchant": expense.get("merchant", ""),
            "description": expense.get("description", ""),
            "payment_method": expense.get("payment_method", "Unknown"),
            "source": expense.get("source", "manual"),
        }
        with self.engine.begin() as connection:
            connection.execute(query, payload)

    def delete_expense(self, expense_id: int, user_id: int) -> None:
        query = text("DELETE FROM expenses WHERE id = :expense_id AND user_id = :user_id")
        with self.engine.begin() as connection:
            connection.execute(query, {"expense_id": expense_id, "user_id": user_id})

    def get_expense(self, expense_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        query = text("SELECT * FROM expenses WHERE id = :expense_id AND user_id = :user_id LIMIT 1")
        with self.engine.connect() as connection:
            result = connection.execute(query, {"expense_id": expense_id, "user_id": user_id}).mappings().first()
            return dict(result) if result else None

    def list_expenses(
        self,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category: Optional[str] = None,
    ) -> pd.DataFrame:
        clauses = ["user_id = :user_id"]
        params: Dict[str, Any] = {"user_id": user_id}
        if start_date:
            clauses.append("txn_date >= :start_date")
            params["start_date"] = start_date
        if end_date:
            clauses.append("txn_date <= :end_date")
            params["end_date"] = end_date
        if category and category != "All":
            clauses.append("category = :category")
            params["category"] = category

        query = text(
            f"""
            SELECT id, txn_date, amount, category, merchant, description, payment_method, source, created_at
            FROM expenses
            WHERE {" AND ".join(clauses)}
            ORDER BY txn_date DESC, created_at DESC
            """
        )
        expenses_df = self._read_dataframe(query, params=params)
        if expenses_df.empty:
            return expenses_df

        expenses_df["id"] = self._coerce_numeric_series(expenses_df["id"]).astype("Int64")
        expenses_df["amount"] = self._coerce_numeric_series(expenses_df["amount"]).fillna(0.0)
        return expenses_df

    def bulk_insert_expenses(self, user_id: int, expenses: pd.DataFrame) -> int:
        if expenses.empty:
            return 0

        rows = []
        for row in expenses.to_dict(orient="records"):
            rows.append(
                {
                    "user_id": user_id,
                    "txn_date": row["txn_date"],
                    "amount": float(row["amount"]),
                    "category": row["category"],
                    "merchant": row.get("merchant", ""),
                    "description": row.get("description", ""),
                    "payment_method": row.get("payment_method", "Unknown"),
                    "source": row.get("source", "csv"),
                }
            )

        query = text(
            """
            INSERT INTO expenses (user_id, txn_date, amount, category, merchant, description, payment_method, source)
            VALUES (:user_id, :txn_date, :amount, :category, :merchant, :description, :payment_method, :source)
            """
        )
        with self.engine.begin() as connection:
            connection.execute(query, rows)
        return len(rows)

    def set_budget(self, user_id: int, budget_month: date, category: str, amount: float) -> None:
        query = text(
            """
            INSERT INTO budgets (user_id, budget_month, category, amount)
            VALUES (:user_id, :budget_month, :category, :amount)
            ON DUPLICATE KEY UPDATE amount = VALUES(amount), updated_at = CURRENT_TIMESTAMP
            """
        )
        with self.engine.begin() as connection:
            connection.execute(
                query,
                {
                    "user_id": user_id,
                    "budget_month": budget_month,
                    "category": category,
                    "amount": float(amount),
                },
            )

    def list_budgets(self, user_id: int, budget_month: Optional[date] = None) -> pd.DataFrame:
        clauses = ["user_id = :user_id"]
        params: Dict[str, Any] = {"user_id": user_id}
        if budget_month:
            clauses.append("budget_month = :budget_month")
            params["budget_month"] = budget_month

        query = text(
            f"""
            SELECT id, budget_month, category, amount, created_at, updated_at
            FROM budgets
            WHERE {" AND ".join(clauses)}
            ORDER BY budget_month DESC, category ASC
            """
        )
        budgets_df = self._read_dataframe(query, params=params)
        if budgets_df.empty:
            return budgets_df

        budgets_df["id"] = self._coerce_numeric_series(budgets_df["id"]).astype("Int64")
        budgets_df["amount"] = self._coerce_numeric_series(budgets_df["amount"]).fillna(0.0)
        return budgets_df

    def create_prediction(
        self,
        user_id: int,
        prediction_month: date,
        model_name: str,
        predicted_amount: float,
        confidence_score: float,
        mae: float,
        rmse: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        query = text(
            """
            INSERT INTO predictions
                (user_id, prediction_month, model_name, predicted_amount, confidence_score, mae, rmse, metadata_json)
            VALUES
                (:user_id, :prediction_month, :model_name, :predicted_amount, :confidence_score, :mae, :rmse, :metadata_json)
            """
        )
        with self.engine.begin() as connection:
            result = connection.execute(
                query,
                {
                    "user_id": user_id,
                    "prediction_month": prediction_month,
                    "model_name": model_name,
                    "predicted_amount": float(predicted_amount),
                    "confidence_score": float(confidence_score),
                    "mae": float(mae),
                    "rmse": float(rmse),
                    "metadata_json": json.dumps(metadata or {}),
                },
            )
            return int(result.lastrowid)

    def list_predictions(self, user_id: int, limit: int = 25) -> pd.DataFrame:
        safe_limit = max(int(limit), 1)
        query = text(
            f"""
            SELECT id, prediction_month, model_name, predicted_amount, confidence_score, mae, rmse, created_at
            FROM predictions
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT {safe_limit}
            """
        )
        predictions_df = self._read_dataframe(query, params={"user_id": user_id})
        if predictions_df.empty:
            return predictions_df

        predictions_df["id"] = self._coerce_numeric_series(predictions_df["id"]).astype("Int64")
        for column in ["predicted_amount", "confidence_score", "mae", "rmse"]:
            predictions_df[column] = self._coerce_numeric_series(predictions_df[column]).fillna(0.0)
        return predictions_df

    def create_alert(
        self,
        user_id: int,
        alert_type: str,
        severity: str,
        message: str,
        related_expense_id: Optional[int] = None,
    ) -> int:
        query = text(
            """
            INSERT INTO alerts (user_id, alert_type, severity, message, related_expense_id)
            VALUES (:user_id, :alert_type, :severity, :message, :related_expense_id)
            """
        )
        with self.engine.begin() as connection:
            result = connection.execute(
                query,
                {
                    "user_id": user_id,
                    "alert_type": alert_type,
                    "severity": severity,
                    "message": message,
                    "related_expense_id": related_expense_id,
                },
            )
            return int(result.lastrowid)

    def list_alerts(self, user_id: int, unresolved_only: bool = False, limit: int = 50) -> pd.DataFrame:
        safe_limit = max(int(limit), 1)
        clauses = ["user_id = :user_id"]
        if unresolved_only:
            clauses.append("is_resolved = FALSE")
        query = text(
            f"""
            SELECT id, alert_type, severity, message, related_expense_id, is_resolved, created_at
            FROM alerts
            WHERE {" AND ".join(clauses)}
            ORDER BY created_at DESC
            LIMIT {safe_limit}
            """
        )
        alerts_df = self._read_dataframe(query, params={"user_id": user_id})
        if alerts_df.empty:
            return alerts_df

        alerts_df["id"] = self._coerce_numeric_series(alerts_df["id"]).astype("Int64")
        alerts_df["related_expense_id"] = self._coerce_numeric_series(alerts_df["related_expense_id"]).astype("Int64")
        alerts_df["is_resolved"] = self._coerce_boolean_series(alerts_df["is_resolved"])
        return alerts_df

    def resolve_alert(self, alert_id: int, user_id: int) -> None:
        query = text("UPDATE alerts SET is_resolved = TRUE WHERE id = :alert_id AND user_id = :user_id")
        with self.engine.begin() as connection:
            connection.execute(query, {"alert_id": alert_id, "user_id": user_id})

    def get_dashboard_summary(self, user_id: int) -> Dict[str, Any]:
        query = text(
            """
            SELECT
                COALESCE(SUM(amount), 0) AS total_spending,
                COALESCE(AVG(amount), 0) AS average_transaction,
                COUNT(*) AS transaction_count,
                COALESCE(MAX(amount), 0) AS largest_expense
            FROM expenses
            WHERE user_id = :user_id
            """
        )
        with self.engine.connect() as connection:
            result = connection.execute(query, {"user_id": user_id}).mappings().first()
            return dict(result) if result else {}
