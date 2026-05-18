"""Feature engineering and regression models for spending prediction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


@dataclass
class ModelResult:
    model_name: str
    mae: float
    rmse: float
    r2: float
    prediction: float


class ExpenseRegressionModel:
    """Build monthly supervised datasets and train regression models."""

    def prepare_monthly_dataset(self, expenses_df: pd.DataFrame) -> pd.DataFrame:
        if expenses_df.empty:
            return pd.DataFrame()

        working_df = expenses_df.copy()
        working_df["txn_date"] = pd.to_datetime(working_df["txn_date"])
        working_df["amount"] = pd.to_numeric(working_df["amount"], errors="coerce").fillna(0.0)
        working_df["month_start"] = working_df["txn_date"].dt.to_period("M").dt.to_timestamp()

        monthly_df = (
            working_df.groupby("month_start")
            .agg(
                total_spend=("amount", "sum"),
                txn_count=("amount", "count"),
                avg_transaction=("amount", "mean"),
                max_transaction=("amount", "max"),
                min_transaction=("amount", "min"),
            )
            .reset_index()
            .sort_values("month_start")
        )

        monthly_df["month_num"] = monthly_df["month_start"].dt.month
        monthly_df["quarter"] = monthly_df["month_start"].dt.quarter
        monthly_df["trend_index"] = np.arange(len(monthly_df))
        monthly_df["rolling_mean_3"] = monthly_df["total_spend"].rolling(3, min_periods=1).mean()
        monthly_df["rolling_std_3"] = monthly_df["total_spend"].rolling(3, min_periods=1).std().fillna(0)
        monthly_df["target_next_month"] = monthly_df["total_spend"].shift(-1)

        return monthly_df.dropna(subset=["target_next_month"]).reset_index(drop=True)

    def split_features_target(self, monthly_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        feature_columns = [
            "total_spend",
            "txn_count",
            "avg_transaction",
            "max_transaction",
            "min_transaction",
            "month_num",
            "quarter",
            "trend_index",
            "rolling_mean_3",
            "rolling_std_3",
        ]
        x = monthly_df[feature_columns]
        y = monthly_df["target_next_month"]
        return x, y

    def _train_model(self, x: pd.DataFrame, y: pd.Series, model, model_name: str) -> ModelResult:
        if len(x) < 2:
            baseline_prediction = float(y.iloc[-1]) if len(y) else 0.0
            return ModelResult(model_name=model_name, mae=0.0, rmse=0.0, r2=0.0, prediction=baseline_prediction)

        test_size = 0.4 if len(x) < 6 else 0.25
        x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=test_size, random_state=42)
        pipeline = Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", model)])
        pipeline.fit(x_train, y_train)
        y_pred = pipeline.predict(x_test)

        next_prediction = float(pipeline.predict(x.tail(1))[0])
        rmse_value = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        return ModelResult(
            model_name=model_name,
            mae=float(mean_absolute_error(y_test, y_pred)),
            rmse=rmse_value,
            r2=float(r2_score(y_test, y_pred)) if len(y_test) > 1 else 0.0,
            prediction=max(next_prediction, 0.0),
        )

    def train_models(self, expenses_df: pd.DataFrame) -> Dict[str, ModelResult]:
        monthly_df = self.prepare_monthly_dataset(expenses_df)
        if monthly_df.empty:
            return {}

        x, y = self.split_features_target(monthly_df)
        linear_result = self._train_model(x, y, LinearRegression(), "Linear Regression")
        forest_result = self._train_model(
            x,
            y,
            RandomForestRegressor(n_estimators=250, random_state=42, max_depth=5),
            "Random Forest",
        )
        return {
            "monthly_dataset": monthly_df,
            "linear_regression": linear_result,
            "random_forest": forest_result,
        }
