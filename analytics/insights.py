"""Insight generation logic."""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd


class InsightEngine:
    """Produces fully local, rule-based spending insights."""

    def generate_insights(
        self,
        expenses_df: pd.DataFrame,
        budgets_df: pd.DataFrame,
        forecast_result: Optional[Dict] = None,
        anomalies_df: Optional[pd.DataFrame] = None,
    ) -> List[str]:
        if expenses_df.empty:
            return ["Start by adding transactions or uploading a CSV statement to unlock insights."]

        insights: List[str] = []
        prepared = expenses_df.copy()
        prepared["txn_date"] = pd.to_datetime(prepared["txn_date"])
        prepared["month"] = prepared["txn_date"].dt.to_period("M")

        monthly_spend = prepared.groupby("month")["amount"].sum().sort_index()
        if len(monthly_spend) >= 2:
            current = monthly_spend.iloc[-1]
            previous = monthly_spend.iloc[-2]
            if previous > 0:
                delta_pct = ((current - previous) / previous) * 100
                direction = "increased" if delta_pct >= 0 else "decreased"
                insights.append(f"Total spending {direction} {abs(delta_pct):.1f}% compared with last month.")

        category_spend = prepared.groupby("category")["amount"].sum().sort_values(ascending=False)
        if not category_spend.empty:
            top_category = category_spend.index[0]
            top_value = category_spend.iloc[0]
            insights.append(f"{top_category} is your highest spending category at {top_value:,.2f}.")

        if not budgets_df.empty:
            latest_budget_month = pd.to_datetime(budgets_df["budget_month"]).max().to_period("M")
            current_month_df = prepared[prepared["month"] == latest_budget_month]
            for _, budget in budgets_df.iterrows():
                if pd.to_datetime(budget["budget_month"]).to_period("M") != latest_budget_month:
                    continue
                if budget["category"] == "Overall":
                    month_spend = current_month_df["amount"].sum()
                    if month_spend > budget["amount"]:
                        insights.append(f"Overall monthly spending exceeded your budget by {month_spend - budget['amount']:,.2f}.")
                else:
                    category_total = current_month_df[current_month_df["category"] == budget["category"]]["amount"].sum()
                    if category_total > budget["amount"]:
                        insights.append(f"{budget['category']} expenses exceed budget by {category_total - budget['amount']:,.2f}.")

        if forecast_result:
            predicted_amount = forecast_result.get("next_month_prediction", 0)
            confidence_score = forecast_result.get("confidence_score", 0)
            insights.append(
                f"Predicted next month spending is {predicted_amount:,.2f} with confidence {confidence_score:.1f}%."
            )

        if anomalies_df is not None and not anomalies_df.empty:
            anomaly_count = int(anomalies_df["is_anomaly"].sum())
            if anomaly_count:
                insights.append(f"{anomaly_count} transactions were flagged as unusual spending patterns.")

        if len(insights) < 3:
            insights.append("You can improve savings by reviewing recurring discretionary categories like Shopping and Entertainment.")

        return insights[:6]
