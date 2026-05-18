"""Plotly chart factories."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


class FinanceCharts:
    """Builds interactive figures for the dashboard."""

    def category_pie(self, category_df: pd.DataFrame):
        if category_df.empty:
            return go.Figure()
        return px.pie(category_df, names="category", values="amount", hole=0.45, title="Category-wise Spending")

    def monthly_bar(self, monthly_df: pd.DataFrame):
        if monthly_df.empty:
            return go.Figure()
        return px.bar(
            monthly_df,
            x="month",
            y="amount",
            title="Monthly Spending",
            color="amount",
            color_continuous_scale="Tealgrn",
        )

    def daily_line(self, daily_df: pd.DataFrame):
        if daily_df.empty:
            return go.Figure()
        return px.line(daily_df, x="day", y="amount", markers=True, title="Daily Spending Trend")

    def monthly_comparison(self, monthly_comparison_df: pd.DataFrame):
        if monthly_comparison_df.empty:
            return go.Figure()
        figure = go.Figure()
        figure.add_bar(x=monthly_comparison_df["month"], y=monthly_comparison_df["amount"], name="Spend")
        figure.add_scatter(
            x=monthly_comparison_df["month"],
            y=monthly_comparison_df["change_pct"],
            yaxis="y2",
            mode="lines+markers",
            name="MoM Change %",
        )
        figure.update_layout(
            title="Monthly Comparison",
            yaxis={"title": "Spend"},
            yaxis2={"title": "MoM Change %", "overlaying": "y", "side": "right"},
        )
        return figure

    def budget_utilization(self, utilization_df: pd.DataFrame):
        if utilization_df.empty:
            return go.Figure()
        melted = utilization_df.melt(id_vars="category", value_vars=["spent", "budget"], var_name="metric", value_name="amount")
        return px.bar(melted, x="category", y="amount", color="metric", barmode="group", title="Budget vs Spend")

    def forecast_chart(self, history_df: pd.DataFrame, forecast_df: pd.DataFrame):
        figure = go.Figure()
        if not history_df.empty:
            figure.add_scatter(x=history_df["month"], y=history_df["amount"], mode="lines+markers", name="Historical Spend")
        if not forecast_df.empty:
            figure.add_scatter(x=forecast_df["month"], y=forecast_df["forecast"], mode="lines+markers", name="Forecast")
        figure.update_layout(title="Expense Forecast")
        return figure

    def anomaly_scatter(self, anomalies_df: pd.DataFrame):
        if anomalies_df.empty:
            return go.Figure()
        return px.scatter(
            anomalies_df,
            x="txn_date",
            y="amount",
            color="is_anomaly",
            symbol="category",
            title="Unusual Spending Detection",
        )
