"""Prediction pipeline and time-series style forecasting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd

from models.expense_model import ExpenseRegressionModel


@dataclass
class ForecastResult:
    next_month_prediction: float
    selected_model: str
    confidence_score: float
    mae: float
    rmse: float
    history_df: pd.DataFrame
    forecast_df: pd.DataFrame
    metrics: List[Dict[str, float]]


class ExpensePredictionPipeline:
    """Select the strongest regression model and build a simple multi-month forecast."""

    def __init__(self) -> None:
        self.regression_model = ExpenseRegressionModel()

    def run(self, expenses_df: pd.DataFrame, periods: int = 3) -> Dict:
        monthly_history = self._monthly_history(expenses_df)
        if monthly_history.empty:
            return {
                "next_month_prediction": 0.0,
                "selected_model": "Insufficient Data",
                "confidence_score": 0.0,
                "mae": 0.0,
                "rmse": 0.0,
                "history_df": pd.DataFrame(columns=["month", "amount"]),
                "forecast_df": pd.DataFrame(columns=["month", "forecast"]),
                "metrics": [],
            }

        model_results = self.regression_model.train_models(expenses_df)
        if not model_results:
            fallback_forecast = self._naive_forecast(monthly_history, periods)
            return {
                "next_month_prediction": float(fallback_forecast.iloc[0]["forecast"]),
                "selected_model": "Naive Average",
                "confidence_score": 45.0,
                "mae": 0.0,
                "rmse": 0.0,
                "history_df": monthly_history,
                "forecast_df": fallback_forecast,
                "metrics": [],
            }

        candidate_results = [model_results["linear_regression"], model_results["random_forest"]]
        best_result = sorted(candidate_results, key=lambda item: (item.mae, item.rmse))[0]
        forecast_df = self._trend_forecast(monthly_history, periods, best_result.prediction)
        confidence_score = max(30.0, min(95.0, 100 - (best_result.mae / max(best_result.prediction, 1)) * 100))

        return {
            "next_month_prediction": best_result.prediction,
            "selected_model": best_result.model_name,
            "confidence_score": confidence_score,
            "mae": best_result.mae,
            "rmse": best_result.rmse,
            "history_df": monthly_history,
            "forecast_df": forecast_df,
            "metrics": [
                {
                    "model": result.model_name,
                    "mae": result.mae,
                    "rmse": result.rmse,
                    "r2": result.r2,
                    "prediction": result.prediction,
                }
                for result in candidate_results
            ],
        }

    def _monthly_history(self, expenses_df: pd.DataFrame) -> pd.DataFrame:
        if expenses_df.empty:
            return pd.DataFrame()

        history_df = expenses_df.copy()
        history_df["txn_date"] = pd.to_datetime(history_df["txn_date"])
        history_df["amount"] = pd.to_numeric(history_df["amount"], errors="coerce").fillna(0.0)
        history_df["month"] = history_df["txn_date"].dt.to_period("M").dt.to_timestamp()
        history_df = history_df.groupby("month", as_index=False)["amount"].sum().sort_values("month")
        return history_df

    def _naive_forecast(self, history_df: pd.DataFrame, periods: int) -> pd.DataFrame:
        average_spend = float(history_df["amount"].tail(3).mean())
        future_months = pd.date_range(history_df["month"].max() + pd.offsets.MonthBegin(1), periods=periods, freq="MS")
        return pd.DataFrame({"month": future_months, "forecast": [average_spend] * periods})

    def _trend_forecast(self, history_df: pd.DataFrame, periods: int, first_prediction: float) -> pd.DataFrame:
        values = history_df["amount"].to_numpy(dtype=float)
        indices = np.arange(len(values))
        if len(values) >= 2:
            slope, intercept = np.polyfit(indices, values, 1)
        else:
            slope, intercept = 0.0, float(values[-1])

        future_indices = np.arange(len(values), len(values) + periods)
        trend_values = (slope * future_indices) + intercept
        future_months = pd.date_range(history_df["month"].max() + pd.offsets.MonthBegin(1), periods=periods, freq="MS")
        forecasts = [max(first_prediction, 0.0)]
        for value in trend_values[1:]:
            forecasts.append(max(float(value), 0.0))
        return pd.DataFrame({"month": future_months, "forecast": forecasts})
