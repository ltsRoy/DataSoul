"""Detects data quality, ML, privacy, and business threats
using statistical checks and pattern matching.
"""

import re
import pandas as pd
import numpy as np
from typing import Any


class ThreatDetector:
    def __init__(self, df: pd.DataFrame, profile: dict):
        self.df = df
        self.profile = profile
        self.threats: list[dict] = []

    def detect_all_threats(self) -> dict:
        """Run all threat detectors and return sorted results"""
        self._detect_missing_value_threats()
        self._detect_duplicate_threats()
        self._detect_inconsistency_threats()
        self._detect_mixed_type_threats()
        self._detect_outlier_threats()
        self._detect_ml_threats()
        self._detect_privacy_threats()
        self._detect_business_threats()

        # Sort by severity
        severity_order = {"critical": 0, "warning": 1, "low": 2}
        self.threats.sort(key=lambda t: (severity_order.get(t["severity"], 3), -t["confidence"]))

        critical = sum(1 for t in self.threats if t["severity"] == "critical")
        warning = sum(1 for t in self.threats if t["severity"] == "warning")
        low = sum(1 for t in self.threats if t["severity"] == "low")

        return {
            "total": len(self.threats),
            "critical": critical,
            "warning": warning,
            "low": low,
            "threats": self.threats,
        }



    def _detect_missing_value_threats(self):
        for col_profile in self.profile.get("columns", []):
            pct = col_profile.get("missing_pct", 0)
            col = col_profile["name"]
            count = col_profile.get("missing", 0)

            if pct == 0:
                continue

            # Determine severity
            is_id = any(kw in col.lower() for kw in ["id", "key", "code", "number"])
            if is_id and count > 0:
                severity = "critical"
                impact = f"{count} records have missing '{col}' — ID fields should NEVER have missing values. This breaks joins, deduplication, and record linkage."
                actions = ["Investigate data pipeline for ingestion failures", f"Cross-reference with source system to recover missing {col} values", "Flag unrecoverable records as 'unattributed'"]
                confidence = 99
            elif pct > 30:
                severity = "critical"
                impact = f"{count} records ({pct}%) have missing values. Column may lack sufficient data for reliable analysis."
                actions = ["Consider dropping column if non-critical", "Use advanced imputation (MICE/KNN) if keeping", "Create missing indicator column"]
                confidence = 90
            elif pct > 5:
                severity = "warning"
                impact = f"{count} records ({pct}%) have missing values, affecting aggregate calculations and downstream models."
                actions = ["Use median for skewed numeric data, mean for normal", "Use mode for low-cardinality categorical", "Create missing indicator if pattern is informative"]
                confidence = 85
            else:
                severity = "low"
                impact = f"{count} records ({pct}%) have minor missing values."
                actions = ["Standard imputation (median/mode) is safe", "Or drop rows if count is negligible"]
                confidence = 88

            self.threats.append({
                "id": f"mv_{col}",
                "severity": severity,
                "title": f"Missing Values in '{col}' ({pct}%)",
                "column": col,
                "category": "Data Quality",
                "impact": impact,
                "confidence": confidence,
                "actions": actions,
            })



    def _detect_duplicate_threats(self):
        dup_info = self.profile.get("duplicates", {})
        dup_count = dup_info.get("exact_duplicates", 0)
        if dup_count > 0:
            dup_pct = dup_info.get("duplicate_pct", 0)
            severity = "critical" if dup_pct > 5 else "warning" if dup_pct > 1 else "low"
            self.threats.append({
                "id": "dup_exact",
                "severity": severity,
                "title": f"Duplicate Records ({dup_count} rows, {dup_pct}%)",
                "column": "All columns",
                "category": "Data Quality",
                "impact": f"{dup_count} exact duplicate rows detected. Revenue and count metrics may be inflated.",
                "confidence": 95,
                "actions": ["Review duplicate groups to verify they are true duplicates", "Keep the most recent/complete record", "Investigate ingestion pipeline for duplication source"],
            })



    def _detect_inconsistency_threats(self):
        for col in self.df.select_dtypes(include=["object"]).columns:
            clean = self.df[col].dropna().astype(str)
            if len(clean) == 0:
                continue

            lower_unique = clean.str.lower().nunique()
            actual_unique = clean.nunique()

            if actual_unique > lower_unique and actual_unique <= 100:
                diff = actual_unique - lower_unique
                self.threats.append({
                    "id": f"inc_{col}",
                    "severity": "warning" if diff > 3 else "low",
                    "title": f"Inconsistent Categories in '{col}'",
                    "column": col,
                    "category": "Data Quality",
                    "impact": f"What should be {lower_unique} categories is fragmented into {actual_unique} due to case/spelling variations.",
                    "confidence": 94,
                    "actions": ["Standardize to title case", "Merge fuzzy-matched categories (>85% similarity)", "Create canonical mapping dictionary"],
                })



    def _detect_mixed_type_threats(self):
        for col in self.df.select_dtypes(include=["object"]).columns:
            clean = self.df[col].dropna()
            if len(clean) == 0:
                continue

            numeric_count = clean.apply(lambda x: self._is_numeric(str(x))).sum()
            numeric_pct = numeric_count / len(clean) * 100

            col_lower = str(col).lower()
            if "year" in col_lower:
                year_like = clean.astype(str).str.match(r"^\d{4}(\s*[-–—]\s*\d{4})?$", na=False).sum()
                if year_like / len(clean) > 0.8:
                    continue

            if 20 < numeric_pct < 95:
                self.threats.append({
                    "id": f"mt_{col}",
                    "severity": "critical",
                    "title": f"Mixed Data Types in '{col}'",
                    "column": col,
                    "category": "Data Quality",
                    "impact": f"Column contains {numeric_pct:.0f}% numeric and {100 - numeric_pct:.0f}% string values. Aggregations will fail.",
                    "confidence": 91,
                    "actions": ["Identify and extract the dominant type", "Convert string representations to proper types", "Handle special values ('N/A', 'NULL') as missing"],
                })



    def _detect_outlier_threats(self):
        for col_profile in self.profile.get("columns", []):
            outliers = col_profile.get("outliers", {})
            count = outliers.get("count", 0)
            if count > 0:
                col = col_profile["name"]
                pct = outliers.get("pct", 0)
                severity = "warning" if pct > 1 else "low"
                self.threats.append({
                    "id": f"out_{col}",
                    "severity": severity,
                    "title": f"Outliers in '{col}' ({count} values, {pct}%)",
                    "column": col,
                    "category": "Data Quality",
                    "impact": f"{count} values beyond 1.5×IQR range [{outliers.get('lower_bound')}, {outliers.get('upper_bound')}]. May skew averages.",
                    "confidence": 88,
                    "actions": ["Verify if outliers are legitimate or data errors", "Winsorize at 1st/99th percentile for financial data", "Use RobustScaler for ML pipelines"],
                })

        # --- Cleanlab Advanced OOD Detection for Numeric Columns ---
        try:
            from cleanlab.outlier import OutOfDistribution
            numeric_cols = self.df.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                # Need at least 20 valid rows to fit OOD reliably
                clean_vals = self.df[col].dropna()
                if len(clean_vals) > 20 and clean_vals.nunique() > 1:
                    ood = OutOfDistribution()
                    scores = ood.fit_score(features=clean_vals.values.reshape(-1, 1))
                    
                    # Score < 0.15 is generally considered OOD in cleanlab for 1D
                    ood_mask = scores < 0.15
                    ood_count = int(np.sum(ood_mask))
                    
                    if ood_count > 0:
                        pct = round((ood_count / len(clean_vals)) * 100, 1)
                        self.threats.append({
                            "id": f"cleanlab_ood_{col}",
                            "severity": "warning" if pct > 1 else "low",
                            "title": f"Cleanlab OOD Anomalies in '{col}' ({ood_count} values)",
                            "column": col,
                            "category": "Anomaly Detection",
                            "impact": f"Cleanlab detected {ood_count} out-of-distribution values ({pct}%). These are statistically abnormal and may be corrupted data.",
                            "confidence": 92,
                            "actions": ["Review flagged OOD rows via Cleanlab integration", "Exclude anomalies from ML training", "Check ingestion sensors for glitches"],
                        })
        except ImportError:
            pass
        except Exception as e:
            print(f"[ThreatDetector] Cleanlab OOD detection failed: {e}")



    def _detect_ml_threats(self):
        corr_info = self.profile.get("correlations", {})
        for pair in corr_info.get("pairs", []):
            if abs(pair["correlation"]) > 0.95:
                self.threats.append({
                    "id": f"corr_{pair['col1']}_{pair['col2']}",
                    "severity": "critical",
                    "title": f"Near-Perfect Correlation (r={pair['correlation']})",
                    "column": f"{pair['col1']} ↔ {pair['col2']}",
                    "category": "ML Risk",
                    "impact": f"Features are essentially duplicates (r={pair['correlation']}). One may be derived from the other or a target leakage risk.",
                    "confidence": 97,
                    "actions": ["Verify if one feature is derived from the other", "Check for target leakage", "Drop the less interpretable feature"],
                })
            elif abs(pair["correlation"]) > 0.85:
                self.threats.append({
                    "id": f"corr_{pair['col1']}_{pair['col2']}",
                    "severity": "warning",
                    "title": f"High Feature Correlation (r={pair['correlation']})",
                    "column": f"{pair['col1']} ↔ {pair['col2']}",
                    "category": "ML Risk",
                    "impact": "Features carry nearly identical information. Redundancy increases model complexity.",
                    "confidence": 85,
                    "actions": ["Consider PCA or feature selection", "Drop one if they measure the same thing", "Use regularization (L1/Lasso)"],
                })



    def _detect_privacy_threats(self):
        PII_PATTERNS = {
            "email": (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "Email Addresses"),
            "phone": (r"\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", "Phone Numbers"),
            "ssn": (r"\b\d{3}-\d{2}-\d{4}\b", "SSN/National IDs"),
            "credit_card": (r"\b(?:\d[ -]*){13,16}\b", "Credit Card Numbers"),
        }

        for col in self.df.select_dtypes(include=["object"]).columns:
            sample = self.df[col].dropna().head(200).astype(str)
            if len(sample) == 0:
                continue

            for pii_type, (pattern, label) in PII_PATTERNS.items():
                matches = sample.str.contains(pattern, regex=True, na=False).sum()
                match_pct = matches / len(sample) * 100

                if match_pct > 30:
                    self.threats.append({
                        "id": f"pii_{pii_type}_{col}",
                        "severity": "critical",
                        "title": f"{label} Detected in '{col}'",
                        "column": col,
                        "category": "Privacy",
                        "impact": f"{label} found in {match_pct:.0f}% of sampled values. PII exposure violates GDPR/CCPA and risks regulatory fines.",
                        "confidence": 96,
                        "actions": [f"Hash or tokenize {col}", f"Remove {col} if not needed for analysis", "Add governance tag: PII-" + pii_type.upper()],
                    })



    def _detect_business_threats(self):
        # Check for date columns with gaps
        for col in self.df.columns:
            if any(kw in col.lower() for kw in ["date", "timestamp", "updated", "created", "reported"]):
                try:
                    dates = pd.to_datetime(self.df[col], errors="coerce").dropna()
                    if len(dates) > 10:
                        date_range = (dates.max() - dates.min()).days
                        if date_range > 90:
                            import datetime
                            days_old = (pd.Timestamp.now() - dates.max()).days
                            if days_old > 90:
                                self.threats.append({
                                    "id": f"stale_{col}",
                                    "severity": "warning",
                                    "title": f"Stale Data Detected ({days_old} days old)",
                                    "column": col,
                                    "category": "Business",
                                    "impact": f"Most recent date in '{col}' is {days_old} days old. Decisions may be based on outdated data.",
                                    "confidence": 82,
                                    "actions": ["Verify data pipeline is running", "Add recency warnings to insights", "Recommend fresh data pull"],
                                })
                except Exception:
                    pass

    @staticmethod
    def _is_numeric(s: str) -> bool:
        s = s.replace(",", "").replace("$", "").replace("₹", "").replace("%", "").strip()
        try:
            float(s)
            return True
        except ValueError:
            return False
