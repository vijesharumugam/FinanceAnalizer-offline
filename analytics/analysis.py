"""Business analytics for finance data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd


@dataclass
class KPIBundle:
    total_spending: float
    monthly_spending: float
    average_daily_spend: float
    savings_percentage: float
    budget_utilization: float


class FinanceAnalyzer:
    """Computes the dashboard-ready aggregates."""

    def prepare_expenses(self, expenses_df: pd.DataFrame) -> pd.DataFrame:
        if expenses_df.empty:
            return expenses_df.copy()

        prepared = expenses_df.copy()
        prepared["txn_date"] = pd.to_datetime(prepared["txn_date"])
        prepared["amount"] = pd.to_numeric(prepared["amount"], errors="coerce").fillna(0.0)
        prepared["month"] = prepared["txn_date"].dt.to_period("M").astype(str)
        prepared["day"] = prepared["txn_date"].dt.date
        return prepared

    def compute_kpis(self, expenses_df: pd.DataFrame, budgets_df: pd.DataFrame) -> KPIBundle:
        prepared = self.prepare_expenses(expenses_df)
        if prepared.empty:
            return KPIBundle(0.0, 0.0, 0.0, 0.0, 0.0)

        latest_month = prepared["txn_date"].max().to_period("M")
        current_month_df = prepared[prepared["txn_date"].dt.to_period("M") == latest_month]
        total_spending = float(prepared["amount"].sum())
        monthly_spending = float(current_month_df["amount"].sum())
        active_days = max(current_month_df["day"].nunique(), 1)
        average_daily_spend = monthly_spending / active_days

        overall_budget = 0.0
        if not budgets_df.empty:
            latest_budget = budgets_df.copy()
            latest_budget["budget_month"] = pd.to_datetime(latest_budget["budget_month"])
            matched = latest_budget[
                (latest_budget["budget_month"].dt.to_period("M") == latest_month)
                & (latest_budget["category"] == "Overall")
            ]
            overall_budget = float(matched["amount"].sum())

        budget_utilization = (monthly_spending / overall_budget * 100) if overall_budget else 0.0
        savings_percentage = max(((overall_budget - monthly_spending) / overall_budget) * 100, 0.0) if overall_budget else 0.0

        return KPIBundle(
            total_spending=round(total_spending, 2),
            monthly_spending=round(monthly_spending, 2),
            average_daily_spend=round(average_daily_spend, 2),
            savings_percentage=round(savings_percentage, 2),
            budget_utilization=round(budget_utilization, 2),
        )

    def monthly_spending(self, expenses_df: pd.DataFrame) -> pd.DataFrame:
        prepared = self.prepare_expenses(expenses_df)
        if prepared.empty:
            return pd.DataFrame(columns=["month", "amount"])

        monthly_df = prepared.groupby("month", as_index=False)["amount"].sum()
        return monthly_df.sort_values("month")

    def category_spending(self, expenses_df: pd.DataFrame) -> pd.DataFrame:
        prepared = self.prepare_expenses(expenses_df)
        if prepared.empty:
            return pd.DataFrame(columns=["category", "amount"])

        return prepared.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)

    def daily_trend(self, expenses_df: pd.DataFrame) -> pd.DataFrame:
        prepared = self.prepare_expenses(expenses_df)
        if prepared.empty:
            return pd.DataFrame(columns=["day", "amount"])

        return prepared.groupby("day", as_index=False)["amount"].sum().sort_values("day")

    def monthly_comparison(self, expenses_df: pd.DataFrame) -> pd.DataFrame:
        monthly_df = self.monthly_spending(expenses_df)
        if monthly_df.empty:
            return monthly_df

        monthly_df["change_pct"] = monthly_df["amount"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0) * 100
        return monthly_df

    def budget_utilization(self, expenses_df: pd.DataFrame, budgets_df: pd.DataFrame) -> pd.DataFrame:
        prepared = self.prepare_expenses(expenses_df)
        if prepared.empty or budgets_df.empty:
            return pd.DataFrame(columns=["category", "spent", "budget", "utilization_pct"])

        prepared["month_period"] = prepared["txn_date"].dt.to_period("M")
        latest_period = prepared["month_period"].max()
        current_month_df = prepared[prepared["month_period"] == latest_period]

        spent_by_category = current_month_df.groupby("category", as_index=False)["amount"].sum().rename(columns={"amount": "spent"})
        budgets = budgets_df.copy()
        budgets["budget_month"] = pd.to_datetime(budgets["budget_month"])
        budgets = budgets[budgets["budget_month"].dt.to_period("M") == latest_period]
        budgets = budgets.rename(columns={"amount": "budget"})
        merged = spent_by_category.merge(budgets[["category", "budget"]], on="category", how="left")
        merged["budget"] = merged["budget"].fillna(0.0)
        merged["utilization_pct"] = np.where(merged["budget"] > 0, (merged["spent"] / merged["budget"]) * 100, 0.0)
        return merged.sort_values("utilization_pct", ascending=False)
