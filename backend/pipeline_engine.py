"""
DataSoul Iterative Pipeline
==============================
Implements the "cleaned data → re-profile → compare" loop.
After user transforms data, this re-analyzes it and shows
before/after improvement metrics.
"""

import pandas as pd
import numpy as np
from typing import Optional

from profiler import DataProfiler
from threat_detector import ThreatDetector
from sector_detector import SectorDetector


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
                    "before": round(orig_dim, 1),
                    "after": round(clean_dim, 1),
                    "change": round(clean_dim - orig_dim, 1),
                    "improved": clean_dim > orig_dim,
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
                        "before": orig_missing,
                        "after": clean_missing,
                        "improved": clean_missing < orig_missing,
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
        from llm_engine import get_llm
        from rag_engine import RAGEngine
        from csv_corrector import CSVCorrector

        df = session["df"].copy()
        profile = session.get("profile")
        threats = session.get("threats", {"threats": []})
        audit = []

        if not profile:
            profiler = DataProfiler(df)
            profile = profiler.generate_full_profile()

        llm = get_llm()
        rag = RAGEngine()

        # ─── Step 0: Ask LLM+RAG for intelligent cleaning plan ───
        llm_plan = None
        if llm.is_available:
            try:
                llm_plan = self._get_llm_cleaning_plan(llm, rag, df, profile, threats)
            except Exception as e:
                print(f"[Pipeline] LLM plan generation failed, using defaults: {e}")

        # ─── Step 0.5: CSV Corrector — type fixes, currency, refs ───
        try:
            corrector = CSVCorrector()
            type_audit = corrector._fix_type_issues(df)
            enc_audit = corrector._fix_encoding(df)
            audit.extend(type_audit)
            audit.extend(enc_audit)
        except Exception as e:
            print(f"[Pipeline] CSV correction step failed (non-critical): {e}")

        # ─── Step 1: Remove exact duplicates ───
        before = len(df)
        df = df.drop_duplicates()
        removed = before - len(df)
        if removed > 0:
            reason = "Exact row-level duplicates inflate counts and bias statistical analysis."
            if llm_plan and "duplicate" in llm_plan.lower():
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
            dtype = col_profile.get("dtype", "")

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

            if strategy == "median" and ("float" in dtype or "int" in dtype):
                fill_val = df[col].median()
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
        if llm_plan and any(kw in llm_plan.lower() for kw in ["clip", "cap", "winsoriz", "outlier"]):
            for col_profile in profile.get("columns", []):
                col = col_profile["name"]
                dtype = col_profile.get("dtype", "")
                outliers = col_profile.get("outliers", {})
                outlier_pct = outliers.get("pct", 0)

                if outlier_pct > 2 and ("float" in dtype or "int" in dtype) and col in df.columns:
                    q1 = df[col].quantile(0.01)
                    q99 = df[col].quantile(0.99)
                    clipped = ((df[col] < q1) | (df[col] > q99)).sum()
                    if clipped > 0:
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

        # Store cleaned data
        session["df_transformed"] = df
        session["audit_trail"] = session.get("audit_trail", []) + audit

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
            "original_shape": list(session["df"].shape),
            "cleaned_shape": list(df.shape),
            "llm_powered": llm.is_available,
            "llm_summary": llm_summary,
            "llm_plan": llm_plan[:500] if llm_plan else None,
        }

    def _get_llm_cleaning_plan(self, llm, rag, df, profile, threats) -> str:
        """Ask LLM+RAG for an intelligent cleaning plan for this dataset"""
        import json as _json

        # Get RAG context — sector-specific cleaning knowledge
        rag_context = ""
        if rag.is_ready:
            sector = profile.get("sector", {}).get("sector_name", "General")
            rag_context = rag.get_context_for_prompt(
                f"data cleaning best practices for {sector} dataset with missing values outliers duplicates",
                dataset_profile=profile,
                n_results=5,
            )

        # Build column summary
        col_issues = []
        for cp in profile.get("columns", [])[:15]:
            issues = []
            if cp.get("missing_pct", 0) > 0:
                issues.append(f"{cp['missing_pct']:.1f}% missing")
            if cp.get("outliers", {}).get("pct", 0) > 1:
                issues.append(f"{cp['outliers']['pct']:.1f}% outliers")
            if issues:
                col_issues.append(f"  - {cp['name']} ({cp.get('dtype', '?')}): {', '.join(issues)}")

        threat_summary = []
        for t in threats.get("threats", [])[:5]:
            threat_summary.append(f"  - [{t['severity'].upper()}] {t['title']}")

        prompt = f"""Analyze this dataset and recommend a specific cleaning plan.

DATASET: {len(df)} rows x {len(df.columns)} columns
SECTOR: {profile.get('sector', {}).get('sector_name', 'General')}
HEALTH: {profile.get('quality_score', {}).get('overall', '?')}/100

COLUMNS WITH ISSUES:
{chr(10).join(col_issues) if col_issues else '  None detected'}

ACTIVE THREATS:
{chr(10).join(threat_summary) if threat_summary else '  None'}

{rag_context}

For EACH column with issues, recommend ONE specific action:
- median/mean/mode/zero/unknown/skip for imputation
- clip/cap for outliers
- And give a ONE-LINE reason why

Keep response under 300 words. Be specific to this dataset's sector and context."""

        return llm.generate(
            prompt,
            system="You are a data engineering expert. Give specific, actionable cleaning recommendations. No fluff.",
            temperature=0.2,
            max_tokens=500,
        )

    def _decide_imputation(self, col: str, col_profile: dict, df, llm_plan: str | None) -> tuple[str, str]:
        """Decide imputation strategy — LLM-guided if available, else deterministic"""
        missing_pct = col_profile.get("missing_pct", 0)
        dtype = col_profile.get("dtype", "")
        stats = col_profile.get("stats", {})
        cardinality = col_profile.get("cardinality", "")
        col_lower = col.lower()

        # Check if LLM has a specific recommendation for this column
        if llm_plan:
            plan_lower = llm_plan.lower()
            if col_lower in plan_lower:
                if "skip" in plan_lower[plan_lower.index(col_lower):plan_lower.index(col_lower)+200]:
                    return "skip", f"LLM advised skipping: too much missing data or column not useful"
                if "zero" in plan_lower[plan_lower.index(col_lower):plan_lower.index(col_lower)+200]:
                    return "zero", f"LLM recommends zero-fill: {col} likely represents absence (e.g. discount, count)"
                if "median" in plan_lower[plan_lower.index(col_lower):plan_lower.index(col_lower)+200]:
                    return "median", f"LLM recommends median: robust to skew in {col}"
                if "mean" in plan_lower[plan_lower.index(col_lower):plan_lower.index(col_lower)+200]:
                    return "mean", f"LLM recommends mean: {col} distribution is approximately normal"
                if "mode" in plan_lower[plan_lower.index(col_lower):plan_lower.index(col_lower)+200]:
                    return "mode", f"LLM recommends mode: most common value preserves distribution"
                if "unknown" in plan_lower[plan_lower.index(col_lower):plan_lower.index(col_lower)+200]:
                    return "unknown", f"LLM recommends 'Unknown': missing category may be informative"

        # ─── Deterministic fallback ───
        if missing_pct > 50:
            return "skip", f"Over 50% missing ({missing_pct:.0f}%). Column lacks sufficient signal."

        if "float" in dtype or "int" in dtype:
            if missing_pct < 30:
                skewness = abs(stats.get("skewness", 0))
                if skewness > 1.0:
                    return "median", f"Skewed distribution (skewness={stats.get('skewness', 0):.2f}). Median is robust."
                else:
                    return "mean", f"Normal distribution. Mean imputation is appropriate."
            return "skip", f"Numeric column with {missing_pct:.0f}% missing — too much for safe imputation."

        if dtype == "object":
            if missing_pct < 20 and cardinality in ("Low", "Binary", "Moderate"):
                return "mode", f"Low-cardinality categorical. Mode preserves dominant distribution."
            elif missing_pct < 30:
                return "unknown", f"Categorical with {missing_pct:.0f}% missing. 'Unknown' is safest."
            return "skip", f"High missing rate ({missing_pct:.0f}%) for categorical column."

        return "skip", "Unknown dtype — skipping for safety."

    @staticmethod
    def _extract_llm_reason(llm_plan: str, keyword: str, default: str) -> str:
        """Extract the LLM's reasoning about a specific topic from its plan"""
        lines = llm_plan.split("\n")
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
        )

