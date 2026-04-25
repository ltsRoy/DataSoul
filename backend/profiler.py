"""
DataSoul Data Profiler
=======================
Generates comprehensive dataset profiles: statistics, distributions,
type analysis, missing patterns, cardinality, and quality dimensions.
"""

import pandas as pd
import numpy as np
from typing import Any


class DataProfiler:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.rows, self.cols = df.shape

    def generate_full_profile(self) -> dict:
        """Generate the complete dataset profile"""
        return {
            "overview": self._overview(),
            "columns": self._column_profiles(),
            "missing_summary": self._missing_summary(),
            "duplicates": self._duplicate_analysis(),
            "correlations": self._correlation_analysis(),
            "quality_score": self._calculate_quality_score(),
        }

    def _overview(self) -> dict:
        mem_mb = self.df.memory_usage(deep=True).sum() / (1024 * 1024)
        return {
            "rows": self.rows,
            "cols": self.cols,
            "memory_mb": round(mem_mb, 2),
            "dtypes": {str(k): int(v) for k, v in self.df.dtypes.value_counts().items()},
            "total_missing": int(self.df.isna().sum().sum()),
            "total_missing_pct": round(self.df.isna().sum().sum() / (self.rows * self.cols) * 100, 2),
            "total_duplicates": int(self.df.duplicated().sum()),
        }

    def _column_profiles(self) -> list[dict]:
        """Profile each column individually"""
        profiles = []
        for col in self.df.columns:
            series = self.df[col]
            profile: dict[str, Any] = {
                "name": col,
                "dtype": str(series.dtype),
                "missing": int(series.isna().sum()),
                "missing_pct": round(series.isna().sum() / self.rows * 100, 2),
                "unique": int(series.nunique()),
                "unique_pct": round(series.nunique() / max(self.rows, 1) * 100, 2),
            }

            # Cardinality classification
            nunique = series.nunique()
            if nunique <= 2:
                profile["cardinality"] = "Binary"
            elif nunique <= 10:
                profile["cardinality"] = "Low"
            elif nunique <= 50:
                profile["cardinality"] = "Moderate"
            elif nunique >= self.rows * 0.9:
                profile["cardinality"] = "ID"
            else:
                profile["cardinality"] = "High"

            # Numeric stats
            if pd.api.types.is_numeric_dtype(series):
                clean = series.dropna()
                if len(clean) > 0:
                    profile["stats"] = {
                        "mean": round(float(clean.mean()), 2),
                        "median": round(float(clean.median()), 2),
                        "std": round(float(clean.std()), 2),
                        "min": round(float(clean.min()), 2),
                        "max": round(float(clean.max()), 2),
                        "q1": round(float(clean.quantile(0.25)), 2),
                        "q3": round(float(clean.quantile(0.75)), 2),
                        "skewness": round(float(clean.skew()), 3),
                        "kurtosis": round(float(clean.kurtosis()), 3),
                    }
                    # Outlier detection (IQR)
                    q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
                    iqr = q3 - q1
                    lower = q1 - 1.5 * iqr
                    upper = q3 + 1.5 * iqr
                    outliers = clean[(clean < lower) | (clean > upper)]
                    profile["outliers"] = {
                        "count": int(len(outliers)),
                        "pct": round(len(outliers) / len(clean) * 100, 2),
                        "lower_bound": round(float(lower), 2),
                        "upper_bound": round(float(upper), 2),
                    }
                    # Distribution type
                    skew = clean.skew()
                    if abs(skew) < 0.5:
                        profile["distribution"] = "approximately_normal"
                    elif skew > 0.5:
                        profile["distribution"] = "right_skewed"
                    else:
                        profile["distribution"] = "left_skewed"

            # Categorical stats
            elif pd.api.types.is_object_dtype(series) or pd.api.types.is_categorical_dtype(series):
                clean = series.dropna()
                if len(clean) > 0:
                    top = clean.value_counts().head(5)
                    profile["top_values"] = {str(k): int(v) for k, v in top.items()}
                    profile["mode"] = str(clean.mode().iloc[0]) if not clean.mode().empty else None
                    profile["mode_frequency"] = round(float(top.iloc[0] / len(clean) * 100), 2) if len(top) > 0 else 0

                    # Check for mixed types
                    numeric_parseable = clean.apply(lambda x: self._is_numeric_string(str(x))).sum()
                    if 0 < numeric_parseable < len(clean) * 0.8:
                        profile["issues"] = profile.get("issues", [])
                        profile["issues"].append("mixed_types")
                        profile["numeric_parseable_pct"] = round(numeric_parseable / len(clean) * 100, 1)

            profiles.append(profile)
        return profiles

    def _missing_summary(self) -> dict:
        missing = self.df.isna().sum()
        missing_cols = missing[missing > 0].sort_values(ascending=False)
        return {
            "columns_with_missing": len(missing_cols),
            "total_cells_missing": int(missing.sum()),
            "total_cells": self.rows * self.cols,
            "overall_missing_pct": round(missing.sum() / (self.rows * self.cols) * 100, 2),
            "by_column": [
                {
                    "column": col,
                    "missing": int(count),
                    "missing_pct": round(count / self.rows * 100, 2),
                    "severity": "critical" if count / self.rows > 0.3 else "warning" if count / self.rows > 0.05 else "low"
                }
                for col, count in missing_cols.items()
            ]
        }

    def _duplicate_analysis(self) -> dict:
        dup_count = self.df.duplicated().sum()
        return {
            "exact_duplicates": int(dup_count),
            "duplicate_pct": round(dup_count / self.rows * 100, 2),
            "severity": "critical" if dup_count / self.rows > 0.05 else "warning" if dup_count > 0 else "none",
        }

    def _correlation_analysis(self) -> dict:
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) < 2:
            return {"pairs": [], "note": "Need at least 2 numeric columns"}

        corr = self.df[numeric_cols].corr()
        high_corr = []

        for i in range(len(numeric_cols)):
            for j in range(i + 1, len(numeric_cols)):
                r = corr.iloc[i, j]
                if abs(r) > 0.7:
                    severity = "critical" if abs(r) > 0.95 else "warning" if abs(r) > 0.85 else "info"
                    high_corr.append({
                        "col1": str(numeric_cols[i]),
                        "col2": str(numeric_cols[j]),
                        "correlation": round(float(r), 3),
                        "severity": severity,
                    })

        return {
            "pairs": sorted(high_corr, key=lambda x: abs(x["correlation"]), reverse=True),
            "total_numeric_cols": len(numeric_cols),
        }

    def _calculate_quality_score(self) -> dict:
        """Calculate the 7-dimension Data Health Score"""
        import re

        # Completeness (20%) — missing values
        total_cells = self.rows * self.cols
        missing_pct = self.df.isna().sum().sum() / max(total_cells, 1)
        completeness = max(0, 100 - (missing_pct * 100 * 2.5))

        # Uniqueness (15%) — duplicate rows
        dup_pct = self.df.duplicated().sum() / max(self.rows, 1)
        uniqueness = max(0, 100 - (dup_pct * 100 * 5))

        # Consistency (15%) — inconsistent casing + mixed formats in string cols
        consistency_penalty = 0
        for col in self.df.select_dtypes(include=["object"]).columns:
            clean = self.df[col].dropna().astype(str)
            if len(clean) == 0:
                continue
            # Case inconsistency
            lower_unique = clean.str.lower().str.strip().nunique()
            actual_unique = clean.nunique()
            if actual_unique > lower_unique:
                consistency_penalty += (actual_unique - lower_unique) / max(actual_unique, 1) * 30
            # Trailing/leading whitespace
            has_whitespace = (clean != clean.str.strip()).sum()
            if has_whitespace > 0:
                consistency_penalty += (has_whitespace / len(clean)) * 15
        consistency = max(0, 100 - consistency_penalty)

        # Type Correctness (15%) — numbers stored as strings, embedded annotations
        type_penalty = 0
        type_issues = []
        for col in self.df.select_dtypes(include=["object"]).columns:
            clean = self.df[col].dropna().astype(str)
            if len(clean) == 0:
                continue

            # Check: how many values look numeric (after stripping $, commas, etc.)
            numeric_like = clean.apply(self._is_numeric_string)
            numeric_ratio = numeric_like.sum() / len(clean)
            if numeric_ratio > 0.5:
                # More than half the values are numeric strings -> type mismatch
                type_penalty += numeric_ratio * 25
                type_issues.append({
                    "column": col, "issue": "numeric_as_string",
                    "numeric_ratio": round(float(numeric_ratio), 2),
                })

            # Check: embedded references/annotations like [1], [a], [b], (2)
            has_refs = clean.str.contains(r'\[\w+\]', regex=True, na=False).sum()
            ref_ratio = has_refs / len(clean)
            if ref_ratio > 0.1:
                type_penalty += ref_ratio * 20
                type_issues.append({
                    "column": col, "issue": "embedded_references",
                    "ref_ratio": round(float(ref_ratio), 2),
                })

            # Check: currency symbols that prevent numeric parsing
            has_currency = clean.str.contains(r'[\$\u20b9\u00a3\u20ac\u00a5]', regex=True, na=False).sum()
            currency_ratio = has_currency / len(clean)
            if currency_ratio > 0.3:
                type_penalty += currency_ratio * 15
                type_issues.append({
                    "column": col, "issue": "unparsed_currency",
                    "currency_ratio": round(float(currency_ratio), 2),
                })

        type_correctness = max(0, 100 - type_penalty)

        # Validity (10%) — outliers and impossible values
        outlier_penalty = 0
        for col in self.df.select_dtypes(include=[np.number]).columns:
            clean = self.df[col].dropna()
            if len(clean) > 10:
                q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    outlier_pct = ((clean < q1 - 3 * iqr) | (clean > q3 + 3 * iqr)).sum() / len(clean)
                    outlier_penalty += outlier_pct * 100
        validity = max(0, 100 - outlier_penalty)

        # Accuracy (10%) — near-zero variance, constant columns
        accuracy_penalty = 0
        for col in self.df.select_dtypes(include=[np.number]).columns:
            if self.df[col].std() < 0.001 and self.df[col].notna().sum() > 0:
                accuracy_penalty += 10
        # Also penalize columns where all values are the same string
        for col in self.df.select_dtypes(include=["object"]).columns:
            if self.df[col].nunique() == 1 and self.df[col].notna().sum() > 5:
                accuracy_penalty += 5
        accuracy = max(0, 100 - accuracy_penalty)

        # Timeliness (15%) — check for date columns and recency
        timeliness = 90  # Default good if no date columns
        for col in self.df.columns:
            try:
                parsed = pd.to_datetime(self.df[col], errors="coerce", infer_datetime_format=True)
                if parsed.notna().sum() > len(self.df) * 0.5:
                    # Found a date column — check recency
                    max_date = parsed.max()
                    if pd.notna(max_date):
                        days_old = (pd.Timestamp.now() - max_date).days
                        if days_old > 365 * 2:
                            timeliness = max(50, 90 - min(days_old / 365, 5) * 8)
                    break
            except Exception:
                pass

        # Weighted Score
        overall = (
            completeness * 0.20 +
            uniqueness * 0.15 +
            consistency * 0.15 +
            type_correctness * 0.15 +
            validity * 0.10 +
            accuracy * 0.10 +
            timeliness * 0.15
        )

        grade = "A+" if overall >= 95 else "A" if overall >= 90 else "B" if overall >= 80 else "C" if overall >= 60 else "D" if overall >= 40 else "F"

        result = {
            "overall": round(overall, 1),
            "grade": grade,
            "dimensions": {
                "completeness": {"score": round(completeness, 1), "weight": 0.20},
                "uniqueness": {"score": round(uniqueness, 1), "weight": 0.15},
                "consistency": {"score": round(consistency, 1), "weight": 0.15},
                "type_correctness": {"score": round(type_correctness, 1), "weight": 0.15},
                "validity": {"score": round(validity, 1), "weight": 0.10},
                "accuracy": {"score": round(accuracy, 1), "weight": 0.10},
                "timeliness": {"score": round(timeliness, 1), "weight": 0.15},
            },
        }

        # Attach type issues for the threat detector / corrector to use
        if type_issues:
            result["type_issues"] = type_issues

        return result

    @staticmethod
    def _is_numeric_string(s: str) -> bool:
        s = s.replace(",", "").replace("$", "").replace("₹", "").replace("%", "").strip()
        try:
            float(s)
            return True
        except ValueError:
            return False
