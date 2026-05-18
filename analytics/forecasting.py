"""Forecasting service wrapper."""

from __future__ import annotations

import pandas as pd

from models.prediction_model import ExpensePredictionPipeline


class ForecastService:
    """Thin service layer for forecasting orchestration."""

    def __init__(self) -> None:
        self.pipeline = ExpensePredictionPipeline()

    def generate_forecast(self, expenses_df: pd.DataFrame, periods: int = 3):
        return self.pipeline.run(expenses_df, periods=periods)
