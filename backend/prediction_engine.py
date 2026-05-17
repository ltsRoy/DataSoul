"""
DataSoul — Prediction Engine
================================
ML + LLM hybrid engine for data predictions, trend forecasting,
anomaly detection, and feature engineering suggestions.

Uses scikit-learn for computation, Ollama for interpretation.
"""

import json
import pandas as pd
import numpy as np
from typing import Optional

from llm_engine import get_llm
from rag_engine import get_rag


class PredictionEngine:
    """scikit-learn + Ollama prediction engine"""

    def __init__(self):
        self._llm = get_llm()
        self._rag = get_rag()

    # ═══ PREDICT MISSING VALUES ═══

    def predict_missing(self, df: pd.DataFrame, target_col: str,
                        profile: dict | None = None) -> dict:
        """Use ML to predict missing values in a column, LLM to explain."""
        if target_col not in df.columns:
            return {"status": "error", "message": f"Column '{target_col}' not found"}

        missing_mask = df[target_col].isna()
        missing_count = int(missing_mask.sum())
        if missing_count == 0:
            return {"status": "ok", "message": "No missing values", "predictions": []}

        is_numeric = pd.api.types.is_numeric_dtype(df[target_col])

        # Get feature columns (numeric only for now)
        feature_cols = [c for c in df.select_dtypes(include=[np.number]).columns
                        if c != target_col and df[c].notna().sum() > len(df) * 0.5]

        if len(feature_cols) < 1:
            return self._simple_prediction(df, target_col, is_numeric, profile)

        try:
            from sklearn.impute import KNNImputer
            from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
            from sklearn.preprocessing import LabelEncoder

            train_df = df[~missing_mask].copy()
            predict_df = df[missing_mask].copy()

            if len(train_df) < 10:
                return self._simple_prediction(df, target_col, is_numeric, profile)

            X_train = train_df[feature_cols].fillna(train_df[feature_cols].median())
            X_predict = predict_df[feature_cols].fillna(train_df[feature_cols].median())

            if is_numeric:
                y_train = train_df[target_col]
                model = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
                model.fit(X_train, y_train)
                predictions = model.predict(X_predict)
                score = round(model.score(X_train, y_train), 3)

                importances = dict(zip(feature_cols,
                    [round(float(x), 3) for x in model.feature_importances_]))
                importances = dict(sorted(importances.items(), key=lambda x: -x[1])[:5])

                pred_list = [{"index": int(idx), "predicted_value": round(float(v), 2)}
                             for idx, v in zip(predict_df.index, predictions)]

                result = {
                    "status": "success", "column": target_col, "type": "numeric",
                    "missing_count": missing_count, "model": "RandomForest",
                    "train_score": score, "feature_importance": importances,
                    "predictions": pred_list[:50],
                    "stats": {
                        "mean_predicted": round(float(np.mean(predictions)), 2),
                        "std_predicted": round(float(np.std(predictions)), 2),
                        "min_predicted": round(float(np.min(predictions)), 2),
                        "max_predicted": round(float(np.max(predictions)), 2),
                    },
                }
            else:
                le = LabelEncoder()
                y_train = le.fit_transform(train_df[target_col].astype(str))
                model = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
                model.fit(X_train, y_train)
                predictions = le.inverse_transform(model.predict(X_predict))
                score = round(model.score(X_train, y_train), 3)

                importances = dict(zip(feature_cols,
                    [round(float(x), 3) for x in model.feature_importances_]))
                importances = dict(sorted(importances.items(), key=lambda x: -x[1])[:5])

                pred_list = [{"index": int(idx), "predicted_value": str(v)}
                             for idx, v in zip(predict_df.index, predictions)]

                from collections import Counter
                pred_counts = dict(Counter(predictions).most_common(10))

                result = {
                    "status": "success", "column": target_col, "type": "categorical",
                    "missing_count": missing_count, "model": "RandomForest",
                    "train_score": score, "feature_importance": importances,
                    "predictions": pred_list[:50],
                    "predicted_distribution": {str(k): int(v) for k, v in pred_counts.items()},
                }

            # LLM interpretation
            result["llm_explanation"] = self._explain_predictions(result, profile)
            return result

        except ImportError:
            return self._simple_prediction(df, target_col, is_numeric, profile)
        except Exception as e:
            return {"status": "error", "message": f"Prediction failed: {str(e)}"}

    def _simple_prediction(self, df, col, is_numeric, profile):
        """Fallback: statistical prediction without ML."""
        if is_numeric:
            median = round(float(df[col].median()), 2)
            mean = round(float(df[col].mean()), 2)
            return {
                "status": "success", "column": col, "type": "numeric",
                "model": "statistical_fallback",
                "missing_count": int(df[col].isna().sum()),
                "suggested_fill": median,
                "stats": {"median": median, "mean": mean},
                "llm_explanation": self._explain_simple(col, "median", median, profile),
            }
        else:
            mode = str(df[col].mode().iloc[0]) if not df[col].mode().empty else "Unknown"
            return {
                "status": "success", "column": col, "type": "categorical",
                "model": "statistical_fallback",
                "missing_count": int(df[col].isna().sum()),
                "suggested_fill": mode,
                "llm_explanation": self._explain_simple(col, "mode", mode, profile),
            }

    # ═══ TREND FORECASTING ═══

    def forecast_trend(self, df: pd.DataFrame, date_col: str, value_col: str,
                       periods: int = 10, profile: dict | None = None) -> dict:
        """Simple time-series extrapolation + LLM narrative."""
        if date_col not in df.columns or value_col not in df.columns:
            return {"status": "error", "message": "Column not found"}

        try:
            ts = df[[date_col, value_col]].copy()
            ts[date_col] = pd.to_datetime(ts[date_col], errors="coerce")
            ts = ts.dropna().sort_values(date_col)

            if len(ts) < 5:
                return {"status": "error", "message": "Not enough data points for forecasting"}

            # Simple linear trend
            ts["ordinal"] = (ts[date_col] - ts[date_col].min()).dt.days.astype(float)
            x = ts["ordinal"].values
            y = ts[value_col].values

            coeffs = np.polyfit(x, y, deg=1)
            slope, intercept = float(coeffs[0]), float(coeffs[1])

            # Forecast
            last_day = float(x[-1])
            avg_gap = float(np.mean(np.diff(x))) if len(x) > 1 else 1.0
            forecast_x = [last_day + avg_gap * (i + 1) for i in range(periods)]
            forecast_y = [round(slope * fx + intercept, 2) for fx in forecast_x]

            # Trend stats
            y_mean = float(np.mean(y))
            y_std = float(np.std(y))
            trend_direction = "increasing" if slope > 0 else "decreasing" if slope < 0 else "flat"
            daily_change = round(slope, 4)

            # Moving average
            window = min(7, len(y) // 3) if len(y) > 6 else 1
            ma = pd.Series(y).rolling(window=window).mean().dropna().tolist()

            result = {
                "status": "success", "date_column": date_col, "value_column": value_col,
                "data_points": len(ts), "periods_forecast": periods,
                "trend": {
                    "direction": trend_direction, "slope": round(slope, 4),
                    "daily_change": daily_change,
                    "r_squared": round(float(1 - np.sum((y - (slope * x + intercept))**2) / np.sum((y - y_mean)**2)), 3) if np.sum((y - y_mean)**2) > 0 else 0,
                },
                "historical": {
                    "mean": round(y_mean, 2), "std": round(y_std, 2),
                    "min": round(float(np.min(y)), 2), "max": round(float(np.max(y)), 2),
                    "latest": round(float(y[-1]), 2),
                },
                "forecast": forecast_y,
                "moving_average": [round(v, 2) for v in ma[-20:]],
            }

            result["llm_narrative"] = self._narrate_trend(result, profile)
            return result

        except Exception as e:
            return {"status": "error", "message": f"Forecast failed: {str(e)}"}

    # ═══ ANOMALY PREDICTION ═══

    def detect_anomalies(self, df: pd.DataFrame, col: str,
                         profile: dict | None = None) -> dict:
        """Predict anomalous values using Isolation Forest + LLM reasoning."""
        if col not in df.columns or not pd.api.types.is_numeric_dtype(df[col]):
            return {"status": "error", "message": f"'{col}' must be a numeric column"}

        clean = df[col].dropna()
        if len(clean) < 20:
            return {"status": "error", "message": "Need at least 20 data points"}

        try:
            from sklearn.ensemble import IsolationForest

            values = clean.values.reshape(-1, 1)
            iso = IsolationForest(contamination=0.05, random_state=42)
            labels = iso.fit_predict(values)
            scores = iso.decision_function(values)

            anomaly_mask = labels == -1
            anomaly_values = clean[anomaly_mask].tolist()
            anomaly_indices = clean[anomaly_mask].index.tolist()

            # Statistical context
            q1, q3 = float(clean.quantile(0.25)), float(clean.quantile(0.75))
            iqr = q3 - q1

            result = {
                "status": "success", "column": col,
                "total_values": len(clean), "anomalies_found": int(anomaly_mask.sum()),
                "anomaly_pct": round(anomaly_mask.sum() / len(clean) * 100, 2),
                "anomaly_values": [round(float(v), 2) for v in anomaly_values[:30]],
                "anomaly_indices": anomaly_indices[:30],
                "stats": {
                    "mean": round(float(clean.mean()), 2),
                    "std": round(float(clean.std()), 2),
                    "q1": round(q1, 2), "q3": round(q3, 2), "iqr": round(iqr, 2),
                    "lower_fence": round(q1 - 1.5 * iqr, 2),
                    "upper_fence": round(q3 + 1.5 * iqr, 2),
                },
                "model": "IsolationForest",
            }

            result["llm_analysis"] = self._analyze_anomalies(result, profile)
            return result

        except ImportError:
            # Fallback: IQR-based detection
            q1, q3 = float(clean.quantile(0.25)), float(clean.quantile(0.75))
            iqr = q3 - q1
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outliers = clean[(clean < lower) | (clean > upper)]
            return {
                "status": "success", "column": col, "model": "IQR",
                "anomalies_found": len(outliers),
                "anomaly_pct": round(len(outliers) / len(clean) * 100, 2),
                "anomaly_values": [round(float(v), 2) for v in outliers.head(30).tolist()],
                "stats": {"lower_fence": round(lower, 2), "upper_fence": round(upper, 2)},
            }

    # ═══ FEATURE ENGINEERING SUGGESTIONS ═══

    def suggest_features(self, df: pd.DataFrame, profile: dict | None = None) -> dict:
        """LLM analyzes column relationships and suggests derived features."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        cat_cols = df.select_dtypes(include=["object"]).columns.tolist()

        # Compute correlations for context
        corr_pairs = []
        if len(numeric_cols) >= 2:
            corr = df[numeric_cols].corr()
            for i in range(len(numeric_cols)):
                for j in range(i + 1, len(numeric_cols)):
                    r = float(corr.iloc[i, j])
                    if abs(r) > 0.3:
                        corr_pairs.append({"col1": numeric_cols[i], "col2": numeric_cols[j],
                                           "correlation": round(r, 3)})
            corr_pairs.sort(key=lambda x: -abs(x["correlation"]))

        # Deterministic suggestions
        suggestions = []

        # Date column decomposition
        for col in df.columns:
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                if parsed.notna().sum() > len(df) * 0.5:
                    suggestions.append({
                        "type": "date_decomposition", "source_column": col,
                        "new_features": [f"{col}_year", f"{col}_month", f"{col}_dayofweek", f"{col}_quarter"],
                        "reason": "Extract temporal components for seasonality analysis",
                        "confidence": 0.95,
                    })
            except Exception:
                pass

        # Ratio features for correlated columns
        for pair in corr_pairs[:3]:
            if abs(pair["correlation"]) > 0.5:
                suggestions.append({
                    "type": "ratio", "source_columns": [pair["col1"], pair["col2"]],
                    "new_feature": f"{pair['col1']}_per_{pair['col2']}",
                    "reason": f"High correlation ({pair['correlation']}) suggests a meaningful ratio",
                    "confidence": 0.80,
                })

        # Binning for high-range numeric columns
        for col in numeric_cols:
            clean = df[col].dropna()
            if len(clean) > 0 and clean.max() / max(clean.min(), 0.01) > 100:
                suggestions.append({
                    "type": "binning", "source_column": col,
                    "new_feature": f"{col}_bin",
                    "reason": f"Large value range ({clean.min():.0f} to {clean.max():.0f}) — binning may improve model performance",
                    "confidence": 0.75,
                })

        # LLM suggestions
        if self._llm.is_available:
            llm_suggestions = self._llm_suggest_features(df, numeric_cols, cat_cols, corr_pairs, profile)
            suggestions.extend(llm_suggestions)

        return {
            "status": "success",
            "suggestions": suggestions,
            "numeric_columns": numeric_cols,
            "categorical_columns": cat_cols,
            "correlations": corr_pairs[:10],
            "llm_powered": self._llm.is_available,
        }

    def _llm_suggest_features(self, df, numeric_cols, cat_cols, corr_pairs, profile):
        """Ask LLM for creative feature engineering ideas."""
        rag_ctx = ""
        if self._rag.is_ready and profile:
            sector = profile.get("sector", {}).get("sector_name", "General")
            rag_ctx = self._rag.get_context_for_prompt(
                f"feature engineering for {sector} datasets", dataset_profile=profile, n_results=3)

        col_summary = "Numeric: " + ", ".join(numeric_cols[:10])
        col_summary += "\nCategorical: " + ", ".join(cat_cols[:10])
        if corr_pairs:
            col_summary += "\nCorrelations: " + ", ".join(
                f"{p['col1']}-{p['col2']}({p['correlation']})" for p in corr_pairs[:5])

        prompt = f"""Dataset has {len(df)} rows. Suggest feature engineering ideas.

COLUMNS:
{col_summary}

Sample values (first row): {dict(df.iloc[0]) if len(df) > 0 else 'N/A'}
{f"DOMAIN: {rag_ctx[:400]}" if rag_ctx and "No relevant" not in rag_ctx else ""}

Suggest 3-5 derived features. Return JSON array:
[{{"feature": "name", "formula": "how to compute", "reason": "why useful", "confidence": 0.8}}]
JSON only."""

        try:
            resp = self._llm.generate(prompt, temperature=0.3, max_tokens=500)
            import re
            match = re.search(r'\[.*\]', resp, re.DOTALL)
            if match:
                items = json.loads(match.group())
                return [{"type": "llm_suggested", "new_feature": s["feature"],
                         "formula": s.get("formula", ""), "reason": s.get("reason", ""),
                         "confidence": float(s.get("confidence", 0.7)), "source": "LLM"}
                        for s in items if isinstance(s, dict) and "feature" in s]
        except Exception as e:
            print(f"[Prediction] LLM feature suggestion failed: {e}")
        return []

    # ═══ LLM INTERPRETATION HELPERS ═══

    def _explain_predictions(self, result: dict, profile: dict | None) -> str:
        if not self._llm.is_available:
            return ""
        prompt = f"""Explain these ML predictions briefly (2-3 sentences):
Column: {result['column']} ({result['type']})
Model: {result['model']} (train score: {result.get('train_score', 'N/A')})
Missing values predicted: {result['missing_count']}
Top features: {json.dumps(result.get('feature_importance', {}), default=str)}
Be specific and mention the key drivers."""
        return self._llm.generate(prompt, temperature=0.3, max_tokens=200)

    def _explain_simple(self, col, method, value, profile):
        if not self._llm.is_available:
            return f"Using {method} ({value}) as best estimate for '{col}'."
        prompt = f"Briefly explain why {method}={value} is used for column '{col}' missing values. 1-2 sentences."
        return self._llm.generate(prompt, temperature=0.2, max_tokens=100)

    def _narrate_trend(self, result: dict, profile: dict | None) -> str:
        if not self._llm.is_available:
            d = result["trend"]["direction"]
            return f"The data shows a {d} trend with slope {result['trend']['slope']}."
        prompt = f"""Narrate this trend analysis (2-3 sentences):
Column: {result['value_column']} over {result['date_column']}
Direction: {result['trend']['direction']}, Slope: {result['trend']['slope']}
R²: {result['trend']['r_squared']}, Data points: {result['data_points']}
Historical: mean={result['historical']['mean']}, latest={result['historical']['latest']}
Forecast (next {result['periods_forecast']}): {result['forecast'][:5]}"""
        return self._llm.generate(prompt, temperature=0.3, max_tokens=200)

    def _analyze_anomalies(self, result: dict, profile: dict | None) -> str:
        if not self._llm.is_available:
            return f"Found {result['anomalies_found']} anomalies in '{result['column']}'."
        prompt = f"""Analyze these anomalies (2-3 sentences):
Column: {result['column']}
Anomalies: {result['anomalies_found']} ({result['anomaly_pct']}%)
Sample values: {result['anomaly_values'][:10]}
Normal range: [{result['stats']['lower_fence']}, {result['stats']['upper_fence']}]
Mean: {result['stats']['mean']}, Std: {result['stats']['std']}"""
        return self._llm.generate(prompt, temperature=0.3, max_tokens=200)

    def get_status(self) -> dict:
        try:
            from sklearn import __version__ as sk_ver
            has_sklearn = True
        except ImportError:
            sk_ver = "not installed"
            has_sklearn = False
        return {"engine": "PredictionEngine", "llm_available": self._llm.is_available,
                "rag_available": self._rag.is_ready, "sklearn_version": sk_ver,
                "has_sklearn": has_sklearn}
