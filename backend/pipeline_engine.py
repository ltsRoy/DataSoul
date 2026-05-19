"""Iterative cleaning pipeline — re-profiles data after each transformation
and compares before/after quality metrics.
"""

import pandas as pd
import numpy as np
import json
from typing import Optional

from profiler import DataProfiler
from threat_detector import ThreatDetector
from sector_detector import SectorDetector
from data_cleaners import DataCleaners


class IterativePipeline:
    """Manages the iterative improve-and-re-analyze cycle"""

    def __init__(self):
        pass

    def iterate(self, session: dict) -> dict:
        """Re-profile the cleaned/transformed data and compare with original"""
        # Get both dataframes
        original_df = session["df"]
        cleaned_df = session.get("df_transformed", original_df)

        # Profile the cleaned data
        cleaned_profiler = DataProfiler(cleaned_df)
        cleaned_profile = cleaned_profiler.generate_full_profile()

        # Get original profile (or generate it)
        original_profile = session.get("profile")
        if not original_profile:
            original_profiler = DataProfiler(original_df)
            original_profile = original_profiler.generate_full_profile()

        # Re-detect threats on cleaned data
        threat_detector = ThreatDetector(cleaned_df, cleaned_profile)
        cleaned_threats = threat_detector.detect_all_threats()

        original_threats = session.get("threats", {"threats": [], "total": 0, "critical": 0, "warning": 0, "low": 0})

        # Re-detect sector
        detector = SectorDetector()
        sector = detector.detect(cleaned_df)
        cleaned_profile["sector"] = sector

        # Build comparison
        comparison = self._build_comparison(
            original_df, cleaned_df,
            original_profile, cleaned_profile,
            original_threats, cleaned_threats,
        )

        # Update session with new data
        session["df"] = cleaned_df
        session["profile"] = cleaned_profile
        session["threats"] = cleaned_threats
        session["iteration_count"] = session.get("iteration_count", 0) + 1

        # Clear the transformed df since it's now the main df
        if "df_transformed" in session:
            del session["df_transformed"]

        return {
            "iteration": session["iteration_count"],
            "cleaned_profile": cleaned_profile,
            "cleaned_threats": cleaned_threats,
            "comparison": comparison,
            "status": "success",
            "message": f"Iteration {session['iteration_count']} complete. Cleaned data is now the active dataset.",
        }

    def _build_comparison(self, original_df: pd.DataFrame, cleaned_df: pd.DataFrame,
                          original_profile: dict, cleaned_profile: dict,
                          original_threats: dict, cleaned_threats: dict) -> dict:
        """Build detailed before/after comparison"""

        # Quality scores
        orig_qs = original_profile.get("quality_score", {})
        clean_qs = cleaned_profile.get("quality_score", {})
        orig_score = orig_qs.get("overall", 0)
        clean_score = clean_qs.get("overall", 0)

        # Shape changes
        orig_shape = original_df.shape
        clean_shape = cleaned_df.shape

        # Missing data comparison
        orig_missing = original_profile.get("missing_summary", {})
        clean_missing = cleaned_profile.get("missing_summary", {})

        # Duplicate comparison
        orig_dups = original_profile.get("duplicates", {})
        clean_dups = cleaned_profile.get("duplicates", {})

        # Threat comparison
        orig_threat_count = original_threats.get("total", 0)
        clean_threat_count = cleaned_threats.get("total", 0)
        orig_critical = original_threats.get("critical", 0)
        clean_critical = cleaned_threats.get("critical", 0)

        # Dimension comparison
        dimension_changes = {}
        if orig_qs.get("dimensions") and clean_qs.get("dimensions"):
            for dim_name in orig_qs["dimensions"]:
                orig_dim = orig_qs["dimensions"].get(dim_name, {}).get("score", 0)
                clean_dim = clean_qs["dimensions"].get(dim_name, {}).get("score", 0)
                dimension_changes[dim_name] = {
                    "before": round(float(orig_dim), 1),
                    "after": round(float(clean_dim), 1),
                    "change": round(float(clean_dim - orig_dim), 1),
                    "improved": bool(clean_dim > orig_dim),
                }

        # Column-level changes
        column_changes = self._compare_columns(original_profile, cleaned_profile)

        # Generate improvement narrative
        narrative = self._generate_improvement_narrative(
            orig_score, clean_score,
            orig_threat_count, clean_threat_count,
            orig_critical, clean_critical,
            orig_shape, clean_shape,
            orig_missing, clean_missing,
        )

        return {
            "quality_score": {
                "before": round(orig_score, 1),
                "after": round(clean_score, 1),
                "change": round(clean_score - orig_score, 1),
                "grade_before": orig_qs.get("grade", "N/A"),
                "grade_after": clean_qs.get("grade", "N/A"),
                "improvement_pct": round((clean_score - orig_score) / max(orig_score, 1) * 100, 1),
            },
            "shape": {
                "before": list(orig_shape),
                "after": list(clean_shape),
                "rows_changed": clean_shape[0] - orig_shape[0],
                "cols_changed": clean_shape[1] - orig_shape[1],
            },
            "missing_data": {
                "before_pct": orig_missing.get("overall_missing_pct", 0),
                "after_pct": clean_missing.get("overall_missing_pct", 0),
                "cells_fixed": orig_missing.get("total_cells_missing", 0) - clean_missing.get("total_cells_missing", 0),
            },
            "duplicates": {
                "before": orig_dups.get("exact_duplicates", 0),
                "after": clean_dups.get("exact_duplicates", 0),
                "removed": orig_dups.get("exact_duplicates", 0) - clean_dups.get("exact_duplicates", 0),
            },
            "threats": {
                "before": orig_threat_count,
                "after": clean_threat_count,
                "resolved": max(0, orig_threat_count - clean_threat_count),
                "critical_before": orig_critical,
                "critical_after": clean_critical,
                "critical_resolved": max(0, orig_critical - clean_critical),
            },
            "dimensions": dimension_changes,
            "column_changes": column_changes,
            "narrative": narrative,
        }

    def _compare_columns(self, original_profile: dict, cleaned_profile: dict) -> list[dict]:
        """Compare column-level profiles before and after cleaning"""
        changes = []

        orig_cols = {c["name"]: c for c in original_profile.get("columns", [])}
        clean_cols = {c["name"]: c for c in cleaned_profile.get("columns", [])}

        # Columns that improved
        for col_name, clean_col in clean_cols.items():
            if col_name in orig_cols:
                orig_col = orig_cols[col_name]
                orig_missing = orig_col.get("missing_pct", 0)
                clean_missing = clean_col.get("missing_pct", 0)

                if orig_missing != clean_missing:
                    changes.append({
                        "column": col_name,
                        "metric": "missing_pct",
                        "before": float(orig_missing),
                        "after": float(clean_missing),
                        "improved": bool(clean_missing < orig_missing),
                    })

        # Columns that were dropped
        for col_name in orig_cols:
            if col_name not in clean_cols:
                changes.append({
                    "column": col_name,
                    "metric": "dropped",
                    "before": "present",
                    "after": "removed",
                    "improved": True,  # Assume intentional
                })

        # Columns that were added
        for col_name in clean_cols:
            if col_name not in orig_cols:
                changes.append({
                    "column": col_name,
                    "metric": "added",
                    "before": "absent",
                    "after": "present",
                    "improved": True,
                })

        return changes

    def _generate_improvement_narrative(
        self, orig_score, clean_score,
        orig_threats, clean_threats,
        orig_critical, clean_critical,
        orig_shape, clean_shape,
        orig_missing, clean_missing,
    ) -> str:
        """Generate a natural language improvement summary"""
        parts = []

        score_change = clean_score - orig_score
        if score_change > 0:
            parts.append(f"✅ **Data Health improved from {orig_score}/100 to {clean_score}/100** (+{score_change:.1f} points)")
        elif score_change < 0:
            parts.append(f"⚠️ Data Health decreased from {orig_score}/100 to {clean_score}/100 ({score_change:.1f} points)")
        else:
            parts.append(f"Data Health Score unchanged at {clean_score}/100")

        threats_resolved = orig_threats - clean_threats
        if threats_resolved > 0:
            parts.append(f"🛡️ {threats_resolved} threat(s) resolved ({orig_threats} → {clean_threats})")

        critical_resolved = orig_critical - clean_critical
        if critical_resolved > 0:
            parts.append(f"🔴→✅ {critical_resolved} critical threat(s) eliminated")

        if clean_critical > 0:
            parts.append(f"⚠️ {clean_critical} critical threat(s) still remain — review recommended")

        rows_change = clean_shape[0] - orig_shape[0]
        if rows_change != 0:
            action = "removed" if rows_change < 0 else "added"
            parts.append(f"📊 {abs(rows_change)} rows {action} ({orig_shape[0]:,} → {clean_shape[0]:,})")

        cols_change = clean_shape[1] - orig_shape[1]
        if cols_change != 0:
            action = "removed" if cols_change < 0 else "added"
            parts.append(f"📋 {abs(cols_change)} column(s) {action}")

        orig_miss_pct = orig_missing.get("overall_missing_pct", 0)
        clean_miss_pct = clean_missing.get("overall_missing_pct", 0)
        if orig_miss_pct != clean_miss_pct:
            parts.append(f"🔧 Missing data reduced: {orig_miss_pct}% → {clean_miss_pct}%")

        if score_change > 15:
            parts.append("\n💎 **Excellent improvement!** Your data is significantly more reliable for analysis and decision-making.")
        elif score_change > 5:
            parts.append("\n👍 Good progress. Consider running another iteration to address remaining issues.")
        elif clean_critical > 0:
            parts.append("\n⚡ Critical threats remain. Address these before using this data for business decisions.")

        return "\n".join(parts)

    def auto_clean(self, session: dict) -> dict:
        """Apply auto-cleaning transformations — LLM+RAG augmented when available"""
        import llm_engine as _llm_mod
        from llm_engine import get_llm
        from rag_engine import get_rag
        from csv_corrector import CSVCorrector
        from llm_cleaner import LLMCleaner

        # Re-initialise LLM singleton so it picks up any newly pulled model
        _llm_mod._llm_instance = None

        source_df = session.get("df_transformed", session["df"])
        df = source_df.copy()
        profile = DataProfiler(df).generate_full_profile()
        profile["sector"] = SectorDetector().detect(df)
        threats = ThreatDetector(df, profile).detect_all_threats()
        audit = []

        llm = get_llm()
        rag = get_rag()

        # ─── Step 0: Ask LLM+RAG for intelligent cleaning plan ───
        llm_plan = None
        if llm.is_available:
            try:
                llm_plan = self._get_llm_cleaning_plan(llm, rag, df, profile, threats)
            except Exception as e:
                print(f"[Pipeline] LLM plan generation failed, using defaults: {e}")

        # ─── Step 0.6: Smart Semantic Cleaning (null strings, whitespace, booleans, percentages) ───
        try:
            cleaned_df, semantic_audit = DataCleaners.run_all(df)
            if semantic_audit:
                for col in cleaned_df.columns:
                    df[col] = cleaned_df[col]
                audit.extend(semantic_audit)
                profile = DataProfiler(df).generate_full_profile()
                profile["sector"] = SectorDetector().detect(df)
        except Exception as e:
            print(f"[Pipeline] Semantic cleaning step failed (non-critical): {e}")

        # ─── Step 0.65: LLM-Powered AI Cleaning (pattern discovery + execution) ───
        try:
            llm_cleaner = LLMCleaner(llm)
            if llm_cleaner.is_available:
                print("[Pipeline] Running LLM-powered column analysis...")
                df, llm_clean_audit = llm_cleaner.clean(df, min_confidence=0.75)
                if llm_clean_audit:
                    audit.extend(llm_clean_audit)
                    print(f"[Pipeline] LLM cleaner applied {len(llm_clean_audit)} fix(es)")
                    profile = DataProfiler(df).generate_full_profile()
                    profile["sector"] = SectorDetector().detect(df)
            else:
                print("[Pipeline] LLM not available — skipping AI cleaning layer")
        except Exception as e:
            print(f"[Pipeline] LLM cleaning step failed (non-critical): {e}")

        # ─── Step 0.75: CSV Corrector — type fixes, currency, refs ───
        try:
            corrector = CSVCorrector()
            header_audit = corrector._clean_column_names(df)
            if header_audit:
                profile = DataProfiler(df).generate_full_profile()
                profile["sector"] = SectorDetector().detect(df)
            type_audit = corrector._fix_type_issues(df)
            enc_audit = corrector._fix_encoding(df)
            drop_audit = corrector._drop_empty_reference_columns(df)
            if drop_audit:
                profile = DataProfiler(df).generate_full_profile()
                profile["sector"] = SectorDetector().detect(df)
            audit.extend(header_audit)
            audit.extend(type_audit)
            audit.extend(enc_audit)
            audit.extend(drop_audit)
            if type_audit or enc_audit:
                profile = DataProfiler(df).generate_full_profile()
                profile["sector"] = SectorDetector().detect(df)
        except Exception as e:
            print(f"[Pipeline] CSV correction step failed (non-critical): {e}")

        # -- Step 0.75: Parse date/year columns --
        try:
            date_hints = ["date", "time", "year", "month", "day", "period", "quarter"]
            for col in list(df.select_dtypes(include=["object"]).columns):
                col_lower = col.lower()
                looks_like_date = any(h in col_lower for h in date_hints)

                if not looks_like_date:
                    continue

                clean = df[col].dropna().astype(str).str.strip()
                if len(clean) == 0:
                    continue

                # check for year-only values (e.g. "2020", "2021", "2023")
                year_like = clean.str.match(r"^\d{4}(\.0)?$", na=False)
                year_ratio = year_like.sum() / len(clean)
                if year_ratio > 0.8:
                    df[col] = pd.to_numeric(
                        df[col].astype("string").str.replace(r"\.0$", "", regex=True),
                        errors="coerce"
                    ).astype("Int64")
                    audit.append({
                        "action": "PARSE_YEAR", "column": col,
                        "detail": f"Converted {int(year_like.sum())} year strings to integers",
                        "rows_affected": int(year_like.sum()),
                        "confidence": 95, "source": "deterministic",
                    })
                    continue

                # try full datetime parsing
                try:
                    parsed = pd.to_datetime(clean, format="mixed", dayfirst=False, errors="coerce")
                    parse_ratio = parsed.notna().sum() / len(clean)
                    if parse_ratio > 0.7:
                        df[col] = pd.to_datetime(df[col], format="mixed", dayfirst=False, errors="coerce")
                        converted = int(df[col].notna().sum())
                        audit.append({
                            "action": "PARSE_DATE", "column": col,
                            "detail": f"Parsed {converted} values as datetime (range: {df[col].min()} to {df[col].max()})",
                            "rows_affected": converted,
                            "confidence": 92, "source": "deterministic",
                        })
                except Exception:
                    pass
        except Exception as e:
            print(f"[Pipeline] Date parsing step failed (non-critical): {e}")

        # -- Step 1: Remove exact duplicates --
        before = len(df)
        df = df.drop_duplicates()
        removed = before - len(df)
        if removed > 0:
            reason = "Exact row-level duplicates inflate counts and bias statistical analysis."
            llm_plan_text = self._plan_to_text(llm_plan)
            if llm_plan and "duplicate" in llm_plan_text.lower():
                # Extract LLM's specific reasoning about duplicates
                reason = self._extract_llm_reason(llm_plan, "duplicate", reason)
            audit.append({
                "action": "REMOVE_DUPLICATES",
                "detail": f"Removed {removed} exact duplicate rows",
                "rows_affected": removed,
                "confidence": 99,
                "reasoning": reason,
                "source": "deterministic + LLM-verified" if llm_plan else "deterministic",
            })

        # ─── Step 2: Standardize case in string columns ───
        for col_profile in profile.get("columns", []):
            col = col_profile["name"]
            if col_profile.get("dtype") == "object" and col in df.columns:
                clean = df[col].dropna().astype(str)
                if len(clean) > 0:
                    lower_unique = clean.str.lower().nunique()
                    actual_unique = clean.nunique()
                    if actual_unique > lower_unique and actual_unique <= 50:
                        before_unique = actual_unique
                        df[col] = df[col].astype(str).str.strip().str.title()
                        after_unique = df[col].nunique()
                        audit.append({
                            "action": "STANDARDIZE_CASE",
                            "column": col,
                            "detail": f"Standardized case: {before_unique} -> {after_unique} unique values",
                            "rows_affected": len(df),
                            "confidence": 94,
                            "reasoning": f"'{col}' has {before_unique} unique values that collapse to {after_unique} when case-normalized, indicating inconsistent data entry.",
                            "source": "deterministic",
                        })

        # ─── Step 3: LLM-guided imputation strategy per column ───
        for col_profile in profile.get("columns", []):
            col = col_profile["name"]
            missing_pct = col_profile.get("missing_pct", 0)
            dtype = col_profile.get("dtype", "").lower()

            if missing_pct <= 0 or col not in df.columns:
                continue

            # Determine strategy — LLM-guided if available
            strategy, reason = self._decide_imputation(
                col, col_profile, df, llm_plan
            )

            if strategy == "skip":
                audit.append({
                    "action": "SKIP_COLUMN",
                    "column": col,
                    "detail": f"Skipped: {missing_pct:.1f}% missing — {reason}",
                    "rows_affected": 0,
                    "confidence": 70,
                    "reasoning": reason,
                    "source": "LLM-advised" if llm_plan else "deterministic",
                })
                continue

            missing_count = int(df[col].isna().sum())
            if missing_count == 0:
                continue

            if strategy == "median_indicator" and ("float" in dtype or "int" in dtype):
                indicator_col = f"{col}_was_missing"
                while indicator_col in df.columns:
                    indicator_col = f"{indicator_col}_flag"
                df[indicator_col] = df[col].isna().astype(int)
                fill_val = df[col].median()
                if "int" in dtype and not float(fill_val).is_integer():
                    df[col] = df[col].astype(float).fillna(fill_val)
                else:
                    df[col] = df[col].fillna(fill_val)
                audit.append({
                    "action": "IMPUTE_MEDIAN_WITH_INDICATOR",
                    "column": col,
                    "detail": f"Added '{indicator_col}' and filled {missing_count} missing values with median ({fill_val:.2f})",
                    "rows_affected": missing_count,
                    "confidence": 84,
                    "reasoning": reason,
                    "source": "LLM-guided" if llm_plan else "deterministic",
                })

            elif strategy == "median" and ("float" in dtype or "int" in dtype):
                fill_val = df[col].median()
                if "int" in dtype and not float(fill_val).is_integer():
                    df[col] = df[col].astype(float).fillna(fill_val)
                else:
                    df[col] = df[col].fillna(fill_val)
                audit.append({
                    "action": "IMPUTE_MEDIAN",
                    "column": col,
                    "detail": f"Filled {missing_count} missing values with median ({fill_val:.2f})",
                    "rows_affected": missing_count,
                    "confidence": 90,
                    "reasoning": reason,
                    "source": "LLM-guided" if llm_plan else "deterministic",
                })

            elif strategy == "mean" and ("float" in dtype or "int" in dtype):
                fill_val = df[col].mean()
                df[col] = df[col].fillna(fill_val)
                audit.append({
                    "action": "IMPUTE_MEAN",
                    "column": col,
                    "detail": f"Filled {missing_count} missing values with mean ({fill_val:.2f})",
                    "rows_affected": missing_count,
                    "confidence": 88,
                    "reasoning": reason,
                    "source": "LLM-guided" if llm_plan else "deterministic",
                })

            elif strategy == "mode" and dtype == "object":
                fill_val = df[col].mode().iloc[0] if not df[col].mode().empty else "Unknown"
                df[col] = df[col].fillna(fill_val)
                audit.append({
                    "action": "IMPUTE_MODE",
                    "column": col,
                    "detail": f"Filled {missing_count} missing values with mode ({fill_val})",
                    "rows_affected": missing_count,
                    "confidence": 86,
                    "reasoning": reason,
                    "source": "LLM-guided" if llm_plan else "deterministic",
                })

            elif strategy == "zero" and ("float" in dtype or "int" in dtype):
                df[col] = df[col].fillna(0)
                audit.append({
                    "action": "IMPUTE_ZERO",
                    "column": col,
                    "detail": f"Filled {missing_count} missing values with 0",
                    "rows_affected": missing_count,
                    "confidence": 80,
                    "reasoning": reason,
                    "source": "LLM-guided",
                })

            elif strategy == "unknown" and dtype == "object":
                df[col] = df[col].fillna("Unknown")
                audit.append({
                    "action": "IMPUTE_UNKNOWN",
                    "column": col,
                    "detail": f"Filled {missing_count} missing values with 'Unknown'",
                    "rows_affected": missing_count,
                    "confidence": 82,
                    "reasoning": reason,
                    "source": "LLM-guided" if llm_plan else "deterministic",
                })

        # ─── Step 4: LLM-suggested outlier capping (if LLM recommended it) ───
        if llm_plan and self._plan_recommends_outlier_capping(llm_plan):
            for col_profile in profile.get("columns", []):
                col = col_profile["name"]
                dtype = col_profile.get("dtype", "").lower()
                outliers = col_profile.get("outliers", {})
                outlier_pct = outliers.get("pct", 0)

                if outlier_pct > 2 and ("float" in dtype or "int" in dtype) and col in df.columns:
                    q1 = df[col].quantile(0.01)
                    q99 = df[col].quantile(0.99)
                    if "int" in str(df[col].dtype).lower():
                        q1 = int(round(q1)) if pd.notna(q1) else q1
                        q99 = int(round(q99)) if pd.notna(q99) else q99
                    
                    clipped = ((df[col] < q1) | (df[col] > q99)).fillna(False).sum()
                    if pd.notna(clipped) and clipped > 0:
                        df[col] = df[col].clip(lower=q1, upper=q99)
                        audit.append({
                            "action": "CLIP_OUTLIERS",
                            "column": col,
                            "detail": f"Capped {int(clipped)} extreme values to [1st, 99th] percentile range [{q1:.2f}, {q99:.2f}]",
                            "rows_affected": int(clipped),
                            "confidence": 78,
                            "reasoning": f"LLM recommended outlier treatment. {outlier_pct:.1f}% values were extreme outliers.",
                            "source": "LLM-guided",
                        })

        # ─── Step 4.5: Time-series forward-fill (for sorted date columns) ───
        try:
            date_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
            for date_col in date_cols:
                if df[date_col].is_monotonic_increasing or df[date_col].is_monotonic_decreasing:
                    # Found a sorted date column — try forward-fill on related numeric columns
                    for other_col in df.select_dtypes(include=[np.number]).columns:
                        missing_count = int(df[other_col].isna().sum())
                        if 0 < missing_count <= len(df) * 0.15:
                            df[other_col] = df[other_col].ffill()
                            filled = missing_count - int(df[other_col].isna().sum())
                            if filled > 0:
                                audit.append({
                                    "action": "FORWARD_FILL",
                                    "column": other_col,
                                    "detail": f"Forward-filled {filled} missing values (time-series context via '{date_col}')",
                                    "rows_affected": filled,
                                    "confidence": 82,
                                    "reasoning": f"Data is sorted by '{date_col}'. Forward-fill propagates the last known value — appropriate for metrics that don't change rapidly.",
                                    "source": "deterministic",
                                })
                    break  # Only use the first sorted date column
        except Exception as e:
            print(f"[Pipeline] Time-series forward-fill failed (non-critical): {e}")

        # Store cleaned data
        session["df_transformed"] = df
        session["audit_trail"] = session.get("audit_trail", []) + audit
        session.pop("profile", None)
        session.pop("threats", None)

        # ─── Step 5: LLM summary of what was done ───
        llm_summary = None
        if llm.is_available and audit:
            try:
                llm_summary = self._generate_cleaning_summary(llm, audit, profile)
            except Exception:
                pass

        return {
            "status": "success",
            "actions_applied": len(audit),
            "audit": audit,
            "original_shape": list(source_df.shape),
            "cleaned_shape": list(df.shape),
            "llm_powered": llm.is_available,
            "llm_summary": llm_summary,
            "llm_plan": self._plan_to_text(llm_plan)[:500] if llm_plan else None,
        }

    def _get_llm_cleaning_plan(self, llm, rag, df, profile, threats) -> dict | None:
        """Ask LLM+RAG for an intelligent cleaning plan for this dataset"""
        # Get RAG context — sector-specific cleaning knowledge
        rag_context = ""
        if rag.is_ready:
            sector = profile.get("sector", {}).get("sector_name", "General")
            rag_context = rag.get_context_for_prompt(
                f"data cleaning best practices for {sector} dataset with missing values outliers duplicates",
                dataset_profile=profile,
                n_results=5,
            )

        # Build column summary with sample values for richer LLM context
        col_issues = []
        for cp in profile.get("columns", [])[:15]:
            issues = []
            if cp.get("missing_pct", 0) > 0:
                issues.append(f"{cp['missing_pct']:.1f}% missing")
            if cp.get("outliers", {}).get("pct", 0) > 1:
                issues.append(f"{cp['outliers']['pct']:.1f}% outliers")
            if issues:
                col_name = cp['name']
                sample_vals = ""
                if col_name in df.columns:
                    sample = df[col_name].dropna().head(5).astype(str).tolist()
                    if sample:
                        sample_vals = f" | Samples: {', '.join(sample[:5])}"
                col_issues.append(f"  - {col_name} ({cp.get('dtype', '?')}): {', '.join(issues)}{sample_vals}")

        threat_summary = []
        for t in threats.get("threats", [])[:5]:
            threat_summary.append(f"  - [{t['severity'].upper()}] {t['title']}")

        # Include value distribution for string columns
        dist_summary = []
        for col in df.select_dtypes(include=["object"]).columns[:5]:
            vc = df[col].dropna().value_counts().head(3)
            if len(vc) > 0:
                top = ", ".join(f"{k}({v})" for k, v in vc.items())
                dist_summary.append(f"  - {col}: {top}")

        prompt = f"""Analyze this dataset and recommend a specific cleaning plan.

DATASET: {len(df)} rows x {len(df.columns)} columns
SECTOR: {profile.get('sector', {}).get('sector_name', 'General')}
HEALTH: {profile.get('quality_score', {}).get('overall', '?')}/100

COLUMNS WITH ISSUES:
{chr(10).join(col_issues) if col_issues else '  None detected'}

VALUE DISTRIBUTIONS (top categories):
{chr(10).join(dist_summary) if dist_summary else '  No categorical columns'}

ACTIVE THREATS:
{chr(10).join(threat_summary) if threat_summary else '  None'}

{rag_context}

Return ONLY valid JSON with this shape:
{{
  "columns": [
    {{
      "column": "exact column name",
      "imputation_strategy": "median|mean|mode|zero|unknown|median_indicator|skip|none",
      "outlier_strategy": "clip|cap|none",
      "reason": "one-line reason"
    }}
  ],
  "dataset_actions": [
    {{"action": "remove_duplicates|none", "reason": "one-line reason"}}
  ]
}}

Include every column with missing values or outliers. Be specific to this dataset's sector and context."""

        raw = llm.generate(
            prompt,
            system="You are a data engineering expert. Return only valid JSON.",
            temperature=0.2,
            max_tokens=500,
            timeout=15,  # Fast-fail: cleaning plan is nice-to-have, not blocking
            json_mode=True,
        )
        try:
            plan = json.loads(raw)
            if isinstance(plan, dict):
                return plan
        except Exception as e:
            print(f"[Pipeline] LLM plan JSON parse failed: {e}")
        return None

    def _decide_imputation(self, col: str, col_profile: dict, df, llm_plan: dict | None) -> tuple[str, str]:
        """Decide imputation strategy — LLM-guided if available, else deterministic"""
        missing_pct = col_profile.get("missing_pct", 0)
        dtype = col_profile.get("dtype", "").lower()
        stats = col_profile.get("stats", {})
        cardinality = col_profile.get("cardinality", "")
        plan_entry = self._get_column_plan(llm_plan, col) if llm_plan else None
        if plan_entry:
            strategy = str(plan_entry.get("imputation_strategy", "none")).lower().strip()
            reason = plan_entry.get("reason") or f"LLM selected {strategy} for {col}"
            if strategy in {"skip", "zero", "median", "mean", "mode", "unknown", "median_indicator"}:
                return strategy, str(reason)

        # ─── Deterministic fallback ───
        if "float" in dtype or "int" in dtype:
            if missing_pct > 50:
                return (
                    "median_indicator",
                    f"Numeric column has {missing_pct:.0f}% missing. Median imputation plus a missingness flag preserves the signal without dropping the field.",
                )
            if missing_pct < 30:
                skewness = abs(stats.get("skewness", 0))
                if skewness > 1.0:
                    return "median", f"Skewed distribution (skewness={stats.get('skewness', 0):.2f}). Median is robust."
                else:
                    return "mean", f"Normal distribution. Mean imputation is appropriate."
            return "skip", f"Numeric column with {missing_pct:.0f}% missing — too much for safe imputation."

        if missing_pct > 50:
            return "skip", f"Over 50% missing ({missing_pct:.0f}%). Column lacks sufficient signal."

        if dtype == "object":
            if missing_pct < 20 and cardinality in ("Low", "Binary", "Moderate"):
                return "mode", f"Low-cardinality categorical. Mode preserves dominant distribution."
            elif missing_pct < 30:
                return "unknown", f"Categorical with {missing_pct:.0f}% missing. 'Unknown' is safest."
            return "skip", f"High missing rate ({missing_pct:.0f}%) for categorical column."

        return "skip", "Unknown dtype — skipping for safety."

    @staticmethod
    def _get_column_plan(llm_plan: dict | None, col: str) -> dict | None:
        if not isinstance(llm_plan, dict):
            return None
        target = col.strip().lower()
        for entry in llm_plan.get("columns", []):
            if isinstance(entry, dict) and str(entry.get("column", "")).strip().lower() == target:
                return entry
        return None

    @staticmethod
    def _plan_to_text(llm_plan) -> str:
        if isinstance(llm_plan, str):
            return llm_plan
        try:
            return json.dumps(llm_plan or {}, ensure_ascii=False)
        except Exception:
            return str(llm_plan or "")

    def _plan_recommends_outlier_capping(self, llm_plan: dict | None) -> bool:
        if not isinstance(llm_plan, dict):
            return False
        for entry in llm_plan.get("columns", []):
            strategy = str(entry.get("outlier_strategy", "")).lower() if isinstance(entry, dict) else ""
            if strategy in {"clip", "cap", "winsorize", "winsorise"}:
                return True
        return False

    def _extract_llm_reason(self, llm_plan, keyword: str, default: str) -> str:
        """Extract the LLM's reasoning about a specific topic from its plan"""
        lines = self._plan_to_text(llm_plan).split("\n")
        for line in lines:
            if keyword.lower() in line.lower() and len(line.strip()) > 10:
                return line.strip().lstrip("-*> ")
        return default

    def _generate_cleaning_summary(self, llm, audit: list, profile: dict) -> str:
        """Generate a natural language summary of cleaning actions taken"""
        actions_text = "\n".join(
            f"- {a['action']}: {a['detail']} (confidence: {a['confidence']}%)"
            for a in audit[:10]
        )
        return llm.generate(
            f"""Summarize these data cleaning actions in 2-3 sentences for a data scientist:

{actions_text}

Dataset sector: {profile.get('sector', {}).get('sector_name', 'General')}
Be concise and mention the most impactful changes.""",
            system="You are DataSoul AI. Summarize cleaning actions briefly.",
            temperature=0.3,
            max_tokens=150,
            timeout=10,  # Fast-fail: summary is optional
        )
