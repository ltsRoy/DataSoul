"""Recommends preprocessing strategies (imputation, encoding, scaling)
based on column profiles and data characteristics.
"""

import pandas as pd
import numpy as np


class StrategyEngine:
    """Recommends data preprocessing strategies per column"""

    def recommend(self, df: pd.DataFrame, profile: dict) -> dict:
        """Generate strategy recommendations for all columns"""
        strategies = []
        pipeline_steps = []

        for col_profile in profile.get("columns", []):
            col = col_profile["name"]
            dtype = col_profile.get("dtype", "")
            missing_pct = col_profile.get("missing_pct", 0)
            cardinality = col_profile.get("cardinality", "")

            col_strategy: dict = {
                "column": col,
                "dtype": dtype,
                "recommendations": [],
            }

            # missing value strategy
            if missing_pct > 0:
                strategy = self._missing_value_strategy(col, col_profile, df)
                col_strategy["recommendations"].append(strategy)
                if strategy.get("pipeline_step"):
                    pipeline_steps.append(strategy["pipeline_step"])

            # encoding strategy
            if dtype == "object" and cardinality not in ("ID", "High"):
                strategy = self._encoding_strategy(col, col_profile, df)
                col_strategy["recommendations"].append(strategy)
                if strategy.get("pipeline_step"):
                    pipeline_steps.append(strategy["pipeline_step"])

            # scaling strategy
            if "float" in dtype or "int" in dtype:
                if cardinality not in ("ID", "Binary"):
                    strategy = self._scaling_strategy(col, col_profile)
                    col_strategy["recommendations"].append(strategy)
                    if strategy.get("pipeline_step"):
                        pipeline_steps.append(strategy["pipeline_step"])

            # feature engineering
            eng = self._feature_engineering(col, col_profile, df)
            if eng:
                col_strategy["recommendations"].append(eng)

            strategies.append(col_strategy)

        return {
            "strategies": strategies,
            "pipeline_steps": pipeline_steps,
            "total_recommendations": sum(len(s["recommendations"]) for s in strategies),
        }

    def _missing_value_strategy(self, col: str, profile: dict, df: pd.DataFrame) -> dict:
        """Recommend imputation strategy based on distribution and type"""
        missing_pct = profile.get("missing_pct", 0)
        dtype = profile.get("dtype", "")
        stats = profile.get("stats", {})
        distribution = profile.get("distribution", "")

        if missing_pct > 50:
            return {
                "type": "missing_value",
                "strategy": "consider_dropping",
                "reason": f"Over 50% missing ({missing_pct}%). Column may lack sufficient signal. Create a missing indicator before dropping.",
                "confidence": 85,
                "alternative": "Advanced imputation (MICE) if domain knowledge suggests the column is critical",
                "pipeline_step": f"# {col}: Consider dropping or creating missing indicator",
            }

        if "float" in dtype or "int" in dtype:
            skewness = abs(stats.get("skewness", 0))
            if skewness > 1.0:
                return {
                    "type": "missing_value",
                    "strategy": "median",
                    "reason": f"Skewness = {stats.get('skewness', 0):.2f} (right-skewed). Median ({stats.get('median', 0)}) is more robust than mean ({stats.get('mean', 0)}).",
                    "confidence": 92,
                    "alternative": "KNN imputation if adjacent features are available",
                    "pipeline_step": f"SimpleImputer(strategy='median')  # {col}",
                }
            else:
                return {
                    "type": "missing_value",
                    "strategy": "mean",
                    "reason": f"Distribution is approximately normal (skewness = {stats.get('skewness', 0):.2f}). Mean imputation is appropriate.",
                    "confidence": 88,
                    "alternative": "Median if outliers are later detected",
                    "pipeline_step": f"SimpleImputer(strategy='mean')  # {col}",
                }

        else:
            cardinality = profile.get("cardinality", "")
            if cardinality in ("Low", "Binary", "Moderate"):
                return {
                    "type": "missing_value",
                    "strategy": "mode",
                    "reason": f"Low cardinality categorical ({profile.get('unique', 0)} unique values). Mode imputation preserves the dominant distribution.",
                    "confidence": 86,
                    "alternative": "Add 'Unknown' category if missing may be informative",
                    "pipeline_step": f"SimpleImputer(strategy='most_frequent')  # {col}",
                }
            else:
                return {
                    "type": "missing_value",
                    "strategy": "add_unknown",
                    "reason": f"High cardinality categorical. Mode imputation may introduce bias. Adding 'Unknown' is safer.",
                    "confidence": 80,
                    "alternative": "Use domain knowledge to assign correct values",
                    "pipeline_step": f"# {col}: fillna('Unknown')",
                }

    def _encoding_strategy(self, col: str, profile: dict, df: pd.DataFrame) -> dict:
        """Recommend categorical encoding strategy"""
        unique = profile.get("unique", 0)
        cardinality = profile.get("cardinality", "")

        if cardinality == "Binary":
            return {
                "type": "encoding",
                "strategy": "label_encoding",
                "reason": f"Binary column ({unique} values). Simple 0/1 label encoding is sufficient.",
                "confidence": 95,
                "pipeline_step": f"LabelEncoder()  # {col} (binary)",
            }
        elif unique <= 10:
            return {
                "type": "encoding",
                "strategy": "one_hot",
                "reason": f"{unique} unique values — one-hot encoding adds minimal dimensionality ({unique} new columns).",
                "confidence": 90,
                "alternative": "Target encoding if the column is ordinal",
                "pipeline_step": f"OneHotEncoder(handle_unknown='ignore')  # {col}",
            }
        elif unique <= 30:
            return {
                "type": "encoding",
                "strategy": "target_encoding",
                "reason": f"{unique} unique values — too many for one-hot. Target encoding preserves information without column explosion.",
                "confidence": 82,
                "alternative": "Ordinal encoding if natural ordering exists",
                "pipeline_step": f"TargetEncoder()  # {col}",
            }
        else:
            return {
                "type": "encoding",
                "strategy": "hash_encoding",
                "reason": f"High cardinality ({unique} values). Hash encoding reduces dimensionality while retaining signal.",
                "confidence": 72,
                "pipeline_step": f"# {col}: high cardinality — consider hash/frequency encoding",
            }

    def _scaling_strategy(self, col: str, profile: dict) -> dict:
        """Recommend feature scaling strategy"""
        stats = profile.get("stats", {})
        outliers = profile.get("outliers", {})
        outlier_pct = outliers.get("pct", 0)
        distribution = profile.get("distribution", "")

        if outlier_pct > 3:
            return {
                "type": "scaling",
                "strategy": "robust_scaler",
                "reason": f"{outlier_pct}% outliers detected. RobustScaler (IQR-based) is resistant to extreme values.",
                "confidence": 92,
                "alternative": "Winsorize first, then StandardScaler",
                "pipeline_step": f"RobustScaler(quantile_range=(25, 75))  # {col}",
            }
        elif distribution == "right_skewed":
            return {
                "type": "scaling",
                "strategy": "log_transform_then_standard",
                "reason": f"Right-skewed distribution (skewness = {stats.get('skewness', 0):.2f}). Log transform normalizes, then StandardScaler centers.",
                "confidence": 86,
                "alternative": "Box-Cox transform for more flexibility",
                "pipeline_step": f"# {col}: np.log1p() → StandardScaler()",
            }
        else:
            return {
                "type": "scaling",
                "strategy": "standard_scaler",
                "reason": "Approximately normal distribution. StandardScaler (z-score normalization) is the standard choice.",
                "confidence": 90,
                "pipeline_step": f"StandardScaler()  # {col}",
            }

    def _feature_engineering(self, col: str, profile: dict, df: pd.DataFrame) -> dict | None:
        """Suggest feature engineering opportunities"""
        # Date decomposition
        if any(kw in col.lower() for kw in ["date", "time", "timestamp"]):
            return {
                "type": "feature_engineering",
                "strategy": "date_decomposition",
                "reason": f"Decompose '{col}' into year, month, day_of_week, quarter, is_weekend for temporal pattern detection.",
                "confidence": 88,
                "new_features": [f"{col}_year", f"{col}_month", f"{col}_day_of_week", f"{col}_quarter", f"{col}_is_weekend"],
            }

        # Amount/revenue interaction features
        if any(kw in col.lower() for kw in ["price", "amount", "revenue", "cost"]):
            return {
                "type": "feature_engineering",
                "strategy": "binning",
                "reason": f"Bin '{col}' into quantile-based segments (Low/Medium/High/Premium) for segment analysis.",
                "confidence": 78,
                "new_features": [f"{col}_segment"],
            }

        return None
