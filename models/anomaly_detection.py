"""IsolationForest based unusual spending detection."""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import IsolationForest


class SpendingAnomalyDetector:
    """Flag unusually large or behaviorally different transactions."""

    def detect(self, expenses_df: pd.DataFrame) -> pd.DataFrame:
        if expenses_df.empty or len(expenses_df) < 8:
            if expenses_df.empty:
                return pd.DataFrame(columns=["txn_date", "amount", "category", "merchant", "is_anomaly", "anomaly_score"])
            fallback = expenses_df.copy()
            fallback["is_anomaly"] = False
            fallback["anomaly_score"] = 0.0
            return fallback

        working_df = expenses_df.copy()
        working_df["txn_date"] = pd.to_datetime(working_df["txn_date"])
        working_df["amount"] = pd.to_numeric(working_df["amount"], errors="coerce").fillna(0.0)
        working_df["day_of_month"] = working_df["txn_date"].dt.day
        working_df["weekday"] = working_df["txn_date"].dt.weekday
        encoded_categories = pd.get_dummies(working_df["category"], prefix="cat")

        feature_df = pd.concat([working_df[["amount", "day_of_month", "weekday"]], encoded_categories], axis=1)
        model = IsolationForest(contamination=0.12, random_state=42)
        predictions = model.fit_predict(feature_df)
        scores = model.decision_function(feature_df)

        working_df["is_anomaly"] = predictions == -1
        working_df["anomaly_score"] = scores
        return working_df.sort_values(["is_anomaly", "amount"], ascending=[False, False])
