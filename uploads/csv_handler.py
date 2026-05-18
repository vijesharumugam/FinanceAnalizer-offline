"""CSV upload parsing and normalization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd

from config import EXPENSE_CATEGORIES


@dataclass
class CSVParseResult:
    cleaned_data: pd.DataFrame
    warnings: List[str]


class CSVExpenseParser:
    """Parse varying bank statement formats into the app schema."""

    category_keywords: Dict[str, str] = {
        "swiggy": "Food",
        "zomato": "Food",
        "uber": "Travel",
        "ola": "Travel",
        "amazon": "Shopping",
        "flipkart": "Shopping",
        "rent": "Rent",
        "netflix": "Entertainment",
        "electricity": "Bills",
        "hospital": "Health",
        "pharmacy": "Health",
        "course": "Education",
        "udemy": "Education",
    }

    def parse(self, file) -> CSVParseResult:
        raw_df = pd.read_csv(file)
        warnings: List[str] = []
        normalized_df = self._normalize_columns(raw_df)

        if normalized_df.empty:
            warnings.append("No valid expense rows were found in the uploaded file.")
            return CSVParseResult(cleaned_data=normalized_df, warnings=warnings)

        normalized_df["txn_date"] = pd.to_datetime(normalized_df["txn_date"], errors="coerce").dt.date
        normalized_df["amount"] = pd.to_numeric(normalized_df["amount"], errors="coerce")
        normalized_df = normalized_df.dropna(subset=["txn_date", "amount"])
        if "flow_type" in normalized_df.columns:
            normalized_df = normalized_df[normalized_df["flow_type"] != "credit"]
        normalized_df["amount"] = normalized_df["amount"].abs()

        normalized_df["merchant"] = normalized_df["merchant"].fillna("").astype(str)
        normalized_df["description"] = normalized_df["description"].fillna("").astype(str)
        normalized_df["payment_method"] = normalized_df["payment_method"].fillna("Bank Statement").astype(str)
        normalized_df["category"] = normalized_df["category"].fillna("").astype(str)
        normalized_df["category"] = normalized_df.apply(self._infer_category, axis=1)
        normalized_df["source"] = "csv"
        normalized_df = normalized_df[normalized_df["amount"] > 0]

        if len(normalized_df) != len(raw_df):
            warnings.append("Some rows were skipped because required fields could not be parsed.")

        return CSVParseResult(cleaned_data=normalized_df, warnings=warnings)

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        lower_map = {column: column.strip().lower() for column in df.columns}
        working_df = df.rename(columns=lower_map).copy()

        date_column = self._pick_column(working_df, ["txn_date", "date", "transaction_date", "posted_date"])
        desc_column = self._pick_column(working_df, ["description", "narration", "details", "remarks"])
        merchant_column = self._pick_column(working_df, ["merchant", "payee", "vendor"])
        category_column = self._pick_column(working_df, ["category"])
        payment_column = self._pick_column(working_df, ["payment_method", "mode", "method"])

        amount_series, flow_type = self._extract_amount_series(working_df)
        if date_column is None or amount_series is None:
            return pd.DataFrame(columns=["txn_date", "amount", "category", "merchant", "description", "payment_method"])

        normalized_df = pd.DataFrame(
            {
                "txn_date": working_df[date_column],
                "amount": amount_series,
                "category": working_df[category_column] if category_column else "",
                "merchant": working_df[merchant_column] if merchant_column else "",
                "description": working_df[desc_column] if desc_column else "",
                "payment_method": working_df[payment_column] if payment_column else "Bank Statement",
                "flow_type": flow_type,
            }
        )
        return normalized_df

    def _pick_column(self, df: pd.DataFrame, candidates: List[str]) -> str | None:
        for candidate in candidates:
            if candidate in df.columns:
                return candidate
        return None

    def _extract_amount_series(self, df: pd.DataFrame) -> Tuple[pd.Series | None, pd.Series | str]:
        if "amount" in df.columns:
            numeric_amount = pd.to_numeric(df["amount"], errors="coerce")
            if (numeric_amount < 0).any():
                flow_type = numeric_amount.apply(lambda value: "debit" if pd.notna(value) and value < 0 else "credit")
            else:
                flow_type = "debit"
            return numeric_amount, flow_type
        if "debit" in df.columns:
            return df["debit"], "debit"
        if "withdrawal" in df.columns:
            return df["withdrawal"], "debit"
        if "credit" in df.columns and "debit" not in df.columns:
            return None, "credit"
        return None, ""

    def _infer_category(self, row: pd.Series) -> str:
        candidate = row.get("category", "").strip().title()
        if candidate in EXPENSE_CATEGORIES:
            return candidate

        searchable_text = f"{row.get('merchant', '')} {row.get('description', '')}".lower()
        for keyword, category in self.category_keywords.items():
            if keyword in searchable_text:
                return category
        return "Others"
