"""
DataSoul — CSV Correction Engine
===================================
AI-powered detection and correction of CSV data issues using Ollama.
"""

import re
import json
import pandas as pd
import numpy as np
from typing import Optional
from collections import Counter

from llm_engine import get_llm
from rag_engine import get_rag

MOJIBAKE_MAP = {
    "\u00e2\u0080\u0099": "'", "\u00e2\u0080\u009c": '"', "\u00e2\u0080\u009d": '"',
    "\u00e2\u0080\u0094": "\u2014", "\u00e2\u0080\u0093": "\u2013", "\u00e2\u0080\u00a6": "\u2026",
    "\u00c3\u00a9": "\u00e9", "\u00c3\u00a8": "\u00e8", "\u00c3\u00bc": "\u00fc",
    "\u00c3\u00b6": "\u00f6", "\u00c3\u00a4": "\u00e4", "\u00c3\u00b1": "\u00f1",
    "\u00c2\u00a3": "\u00a3", "\u00c2\u00a5": "\u00a5", "\u00e2\u0082\u00b9": "\u20b9",
    "\u00c2\u00b0": "\u00b0", "\u00c2\u00a9": "\u00a9", "\u00c2\u00ae": "\u00ae",
    "\x00": "", "\ufeff": "",
}


class CSVCorrector:
    """Ollama-powered CSV data correction engine"""

    AUTO_APPLY_THRESHOLD = 0.90
    SUGGEST_THRESHOLD = 0.60

    def __init__(self):
        self._llm = get_llm()
        self._rag = get_rag()

    # ═══ PUBLIC API ═══

    def analyze(self, df: pd.DataFrame, profile: dict | None = None) -> dict:
        """Full analysis pass — detect all correctable issues without modifying data."""
        results = {
            "columns_analyzed": 0, "issues_found": 0,
            "corrections": [], "encoding_issues": [],
            "format_issues": [], "category_merges": [],
            "type_issues": [],
            "llm_powered": self._llm.is_available,
        }

        results["encoding_issues"] = self._detect_encoding_issues(df)
        results["issues_found"] += len(results["encoding_issues"])

        results["format_issues"] = self._detect_format_issues(df)
        results["issues_found"] += len(results["format_issues"])

        results["type_issues"] = self._detect_type_issues(df)
        results["issues_found"] += len(results["type_issues"])

        for col in df.select_dtypes(include=["object"]).columns:
            clean = df[col].dropna().astype(str)
            if len(clean) == 0 or clean.nunique() > 500:
                continue
            results["columns_analyzed"] += 1

            merges = self._analyze_categories(df, col, profile)
            if merges:
                results["category_merges"].extend(merges)
                results["issues_found"] += len(merges)

            if clean.nunique() <= 100:
                corrections = self._analyze_column_values(df, col, profile)
                if corrections:
                    results["corrections"].extend(corrections)
                    results["issues_found"] += len(corrections)

        return results

    def auto_correct(self, df: pd.DataFrame, profile: dict | None = None,
                     threshold: float | None = None) -> dict:
        """Full auto-correction pipeline. Returns modified DataFrame + audit trail."""
        threshold = threshold or self.AUTO_APPLY_THRESHOLD
        df_out = df.copy()
        audit = []

        audit.extend(self._fix_encoding(df_out))
        audit.extend(self._fix_type_issues(df_out))  # Strip $, refs, convert types
        audit.extend(self._fix_formats(df_out, profile))
        audit.extend(self._merge_categories(df_out, profile, threshold))
        audit.extend(self._correct_values(df_out, profile, threshold))

        return {
            "status": "success", "df": df_out,
            "corrections_applied": len(audit), "audit": audit,
            "original_shape": list(df.shape),
            "corrected_shape": list(df_out.shape),
            "llm_powered": self._llm.is_available,
        }

    def apply_corrections(self, df: pd.DataFrame, corrections: list[dict]) -> dict:
        """Apply a user-approved list of corrections."""
        df_out = df.copy()
        applied = []
        for corr in corrections:
            col, old_val, new_val = corr.get("column"), corr.get("old_value"), corr.get("new_value")
            if not col or col not in df_out.columns:
                continue
            mask = df_out[col].astype(str) == str(old_val)
            count = int(mask.sum())
            if count > 0:
                df_out.loc[mask, col] = new_val
                applied.append({
                    "action": "VALUE_CORRECTION", "column": col,
                    "old_value": old_val, "new_value": new_val,
                    "rows_affected": count, "source": "user_approved",
                })
        return {"status": "success", "df": df_out, "corrections_applied": len(applied), "audit": applied}

    # ═══ ENCODING ═══

    def _detect_encoding_issues(self, df: pd.DataFrame) -> list[dict]:
        issues = []
        for col in df.select_dtypes(include=["object"]).columns:
            sample = df[col].dropna().astype(str)
            if len(sample) == 0:
                continue
            concat = " ".join(sample.head(500).tolist())
            found = []
            for bad, good in MOJIBAKE_MAP.items():
                if bad in concat:
                    found.append({"pattern": bad, "replacement": good, "occurrences": concat.count(bad)})
            if found:
                issues.append({"column": col, "type": "encoding", "patterns": found, "confidence": 0.95, "auto_fixable": True})
        return issues

    def _fix_encoding(self, df: pd.DataFrame) -> list[dict]:
        audit = []
        for col in df.select_dtypes(include=["object"]).columns:
            total = 0
            for bad, good in MOJIBAKE_MAP.items():
                mask = df[col].astype(str).str.contains(re.escape(bad), na=False)
                count = int(mask.sum())
                if count > 0:
                    df[col] = df[col].astype(str).str.replace(bad, good, regex=False)
                    total += count
            if total > 0:
                audit.append({"action": "FIX_ENCODING", "column": col,
                              "detail": f"Fixed {total} encoding artifacts", "rows_affected": total,
                              "confidence": 95, "source": "deterministic"})
        return audit

    # ═══ FORMAT DETECTION & REPAIR ═══

    def _detect_format_issues(self, df: pd.DataFrame) -> list[dict]:
        issues = []
        for col in df.select_dtypes(include=["object"]).columns:
            sample = df[col].dropna().astype(str).head(200)
            if len(sample) == 0:
                continue

            date_patterns = {
                "DD/MM/YYYY": r"\d{1,2}/\d{1,2}/\d{4}",
                "YYYY-MM-DD": r"\d{4}-\d{1,2}-\d{1,2}",
                "DD.MM.YYYY": r"\d{1,2}\.\d{1,2}\.\d{4}",
            }
            detected = {}
            for fmt, pat in date_patterns.items():
                m = sample.str.match(pat, na=False).sum()
                if m > 0:
                    detected[fmt] = int(m)
            if len(detected) > 1:
                issues.append({"column": col, "type": "mixed_date_format",
                               "formats_found": detected, "confidence": 0.88, "auto_fixable": True})

            comma_num = sample.str.match(r"^\d{1,3}(,\d{3})+(\.\d+)?$", na=False).sum()
            dot_num = sample.str.match(r"^\d{1,3}(\.\d{3})+(,\d+)?$", na=False).sum()
            if comma_num > 0 and dot_num > 0:
                issues.append({"column": col, "type": "mixed_number_format",
                               "comma_count": int(comma_num), "dot_count": int(dot_num),
                               "confidence": 0.85, "auto_fixable": True})
        return issues

    def _fix_formats(self, df: pd.DataFrame, profile: dict | None) -> list[dict]:
        audit = []
        for issue in self._detect_format_issues(df):
            col = issue["column"]
            if not issue.get("auto_fixable"):
                continue
            if issue["type"] == "mixed_date_format":
                try:
                    parsed = pd.to_datetime(df[col], infer_datetime_format=True, errors="coerce")
                    valid = parsed.notna().sum()
                    if valid >= df[col].notna().sum() * 0.8:
                        df[col] = parsed.dt.strftime("%Y-%m-%d").where(parsed.notna(), df[col])
                        audit.append({"action": "STANDARDIZE_DATE", "column": col,
                                      "detail": f"Standardized {valid} dates to ISO 8601",
                                      "rows_affected": int(valid), "confidence": 88, "source": "deterministic"})
                except Exception:
                    pass
            elif issue["type"] == "mixed_number_format":
                try:
                    cleaned = df[col].astype(str).str.replace(",", "", regex=False)
                    numeric = pd.to_numeric(cleaned, errors="coerce")
                    if numeric.notna().sum() > df[col].notna().sum() * 0.7:
                        df[col] = cleaned
                        audit.append({"action": "STANDARDIZE_NUMBER", "column": col,
                                      "detail": "Removed comma-separators for numeric consistency",
                                      "rows_affected": int(numeric.notna().sum()), "confidence": 85, "source": "deterministic"})
                except Exception:
                    pass
        return audit

    # ═══ CATEGORY MERGING (LLM) ═══

    def _analyze_categories(self, df: pd.DataFrame, col: str, profile: dict | None) -> list[dict]:
        clean = df[col].dropna().astype(str)
        uniques = clean.unique().tolist()
        if len(uniques) < 2 or len(uniques) > 100:
            return []

        lower_map = {}
        for val in uniques:
            lower_map.setdefault(val.strip().lower(), []).append(val)

        merges = []
        for key, variants in lower_map.items():
            if len(variants) <= 1:
                continue
            counts = {v: int((clean == v).sum()) for v in variants}
            canonical = max(counts, key=counts.get)
            for v in variants:
                if v != canonical:
                    merges.append({"column": col, "old_value": v, "new_value": canonical,
                                   "count": counts[v], "confidence": 0.95,
                                   "reason": f"Case variant of '{canonical}'", "type": "case_variant"})

        if self._llm.is_available and len(uniques) <= 60:
            merges.extend(self._llm_find_merges(col, uniques, profile))
        return merges

    def _llm_find_merges(self, col: str, uniques: list[str], profile: dict | None) -> list[dict]:
        rag_ctx = ""
        if self._rag.is_ready and profile:
            sector = profile.get("sector", {}).get("sector_name", "General")
            rag_ctx = self._rag.get_context_for_prompt(
                f"standard naming for {col} in {sector}", dataset_profile=profile, n_results=3)

        vals = "\n".join(f'  - "{v}"' for v in sorted(uniques)[:60])
        prompt = f"""Analyze these values from column "{col}" and identify typos/duplicates to merge.

VALUES:
{vals}
{f"CONTEXT: {rag_ctx[:400]}" if rag_ctx and "No relevant" not in rag_ctx else ""}

Return a JSON array: [{{"old": "variant", "new": "canonical", "reason": "why"}}]
Only flag clear duplicates (>80% confident). If none, return []. JSON only."""

        try:
            resp = self._llm.generate(prompt, temperature=0.1, max_tokens=600)
            match = re.search(r'\[.*\]', resp, re.DOTALL)
            if match:
                items = json.loads(match.group())
                return [{"column": col, "old_value": s["old"], "new_value": s["new"],
                         "count": 0, "confidence": 0.82,
                         "reason": s.get("reason", "LLM-detected duplicate"), "type": "llm_merge"}
                        for s in items if isinstance(s, dict) and "old" in s and "new" in s]
        except Exception as e:
            print(f"[CSVCorrector] LLM merge failed for '{col}': {e}")
        return []

    def _merge_categories(self, df: pd.DataFrame, profile: dict | None, threshold: float) -> list[dict]:
        audit = []
        for col in df.select_dtypes(include=["object"]).columns:
            for m in self._analyze_categories(df, col, profile):
                if m["confidence"] >= threshold and m["old_value"] != m["new_value"]:
                    mask = df[col].astype(str) == m["old_value"]
                    count = int(mask.sum())
                    if count > 0:
                        df.loc[mask, col] = m["new_value"]
                        audit.append({"action": "MERGE_CATEGORY", "column": col,
                                      "detail": f"'{m['old_value']}' -> '{m['new_value']}' ({count} rows)",
                                      "rows_affected": count, "confidence": int(m["confidence"] * 100),
                                      "source": "LLM-guided" if m["type"] == "llm_merge" else "deterministic"})
        return audit

    # ═══ VALUE CORRECTION (LLM) ═══

    def _analyze_column_values(self, df: pd.DataFrame, col: str, profile: dict | None) -> list[dict]:
        if not self._llm.is_available:
            return []
        clean = df[col].dropna().astype(str)
        if len(clean) == 0:
            return []

        vc = clean.value_counts()
        sample = list(set(vc.head(20).index.tolist() + vc.tail(min(20, len(vc))).index.tolist()))[:40]

        rag_ctx = ""
        if self._rag.is_ready and profile:
            sector = profile.get("sector", {}).get("sector_name", "General")
            rag_ctx = self._rag.get_context_for_prompt(
                f"valid values for {col} in {sector}", dataset_profile=profile, n_results=2)

        vals = "\n".join(f'  {i+1}. "{v}" ({int(vc.get(v, 0))}x)' for i, v in enumerate(sample))
        prompt = f"""Column "{col}" — identify errors and suggest corrections.

VALUES (with frequency):
{vals}
{f"CONTEXT: {rag_ctx[:300]}" if rag_ctx and "No relevant" not in rag_ctx else ""}

Return JSON: [{{"value": "wrong", "correction": "right", "confidence": 0.85, "reason": "why"}}]
Only clear errors (confidence>0.7). If none, return []. JSON only."""

        try:
            resp = self._llm.generate(prompt, temperature=0.1, max_tokens=600)
            match = re.search(r'\[.*\]', resp, re.DOTALL)
            if match:
                items = json.loads(match.group())
                return [{"column": col, "old_value": s["value"], "new_value": s["correction"],
                         "count": int(vc.get(s["value"], 0)),
                         "confidence": round(float(s.get("confidence", 0.75)), 2),
                         "reason": s.get("reason", "LLM-detected error"), "type": "value_correction"}
                        for s in items if isinstance(s, dict) and "value" in s and "correction" in s
                        and float(s.get("confidence", 0)) >= self.SUGGEST_THRESHOLD]
        except Exception as e:
            print(f"[CSVCorrector] LLM value analysis failed for '{col}': {e}")
        return []

    def _correct_values(self, df: pd.DataFrame, profile: dict | None, threshold: float) -> list[dict]:
        audit = []
        for col in df.select_dtypes(include=["object"]).columns:
            clean = df[col].dropna().astype(str)
            if len(clean) == 0 or clean.nunique() > 100:
                continue
            for corr in self._analyze_column_values(df, col, profile):
                if corr["confidence"] >= threshold:
                    mask = df[col].astype(str) == corr["old_value"]
                    count = int(mask.sum())
                    if count > 0:
                        df.loc[mask, col] = corr["new_value"]
                        audit.append({"action": "VALUE_CORRECTION", "column": col,
                                      "detail": f"'{corr['old_value']}' -> '{corr['new_value']}' ({count} rows)",
                                      "rows_affected": count, "confidence": int(corr["confidence"] * 100),
                                      "source": "LLM-guided"})
        return audit

    # === TYPE ISSUES (currency strings, embedded refs, numeric-as-string) ===

    def _detect_type_issues(self, df: pd.DataFrame) -> list[dict]:
        """Detect columns where values look numeric but are stored as strings."""
        issues = []
        for col in df.select_dtypes(include=["object"]).columns:
            clean = df[col].dropna().astype(str)
            if len(clean) == 0:
                continue

            # Check for currency symbols ($, Rs, etc.)
            has_currency = clean.str.contains(r'[\$\u20b9\u00a3\u20ac\u00a5]', regex=True, na=False).sum()
            currency_ratio = has_currency / len(clean)

            # Check for embedded references like [1], [a], [2][5]
            has_refs = clean.str.contains(r'\[\w+\]', regex=True, na=False).sum()
            ref_ratio = has_refs / len(clean)

            # Check if values are numeric after stripping $, commas, refs
            stripped = clean.str.replace(r'[\$\u20b9\u00a3\u20ac\u00a5,]', '', regex=True)
            stripped = stripped.str.replace(r'\[\w+\]', '', regex=True).str.strip()
            numeric_count = pd.to_numeric(stripped, errors='coerce').notna().sum()
            numeric_ratio = numeric_count / len(clean)

            if currency_ratio > 0.3 and numeric_ratio > 0.5:
                issues.append({
                    "column": col, "type": "currency_as_string",
                    "currency_ratio": round(float(currency_ratio), 2),
                    "numeric_ratio": round(float(numeric_ratio), 2),
                    "suggestion": "Strip currency symbols and convert to numeric",
                    "confidence": 0.95, "auto_fixable": True,
                })
            elif ref_ratio > 0.1:
                issues.append({
                    "column": col, "type": "embedded_references",
                    "ref_ratio": round(float(ref_ratio), 2),
                    "numeric_after_strip": round(float(numeric_ratio), 2),
                    "suggestion": "Remove reference annotations like [1], [a]",
                    "confidence": 0.92, "auto_fixable": True,
                })
            elif numeric_ratio > 0.7:
                issues.append({
                    "column": col, "type": "numeric_as_string",
                    "numeric_ratio": round(float(numeric_ratio), 2),
                    "suggestion": "Convert to numeric type",
                    "confidence": 0.90, "auto_fixable": True,
                })

        return issues

    def _fix_type_issues(self, df: pd.DataFrame) -> list[dict]:
        """Fix type issues: strip currency, remove refs, convert to numeric."""
        audit = []

        for col in list(df.select_dtypes(include=["object"]).columns):
            clean = df[col].dropna().astype(str)
            if len(clean) == 0:
                continue

            # Step 1: Remove embedded reference annotations [1], [a], [b], [17]
            has_refs = clean.str.contains(r'\[\w+\]', regex=True, na=False).sum()
            if has_refs > len(clean) * 0.1:
                original_vals = df[col].copy()
                df[col] = df[col].astype(str).str.replace(r'\[\w+\]', '', regex=True).str.strip()
                changed = (df[col] != original_vals.astype(str)).sum()
                if changed > 0:
                    audit.append({
                        "action": "STRIP_REFERENCES", "column": col,
                        "detail": f"Removed reference annotations like [1],[a] from {int(changed)} values",
                        "rows_affected": int(changed), "confidence": 92,
                        "source": "deterministic",
                    })

            # Step 2: Strip currency symbols and comma-separators, then convert
            clean = df[col].dropna().astype(str)
            has_currency = clean.str.contains(r'[\$\u20b9\u00a3\u20ac\u00a5]', regex=True, na=False).sum()
            if has_currency > len(clean) * 0.3:
                stripped = df[col].astype(str).str.replace(r'[\$\u20b9\u00a3\u20ac\u00a5,\s]', '', regex=True)
                # Also handle annotations that might remain
                stripped = stripped.str.replace(r'\[\w+\]', '', regex=True).str.strip()
                numeric = pd.to_numeric(stripped, errors='coerce')
                convert_ratio = numeric.notna().sum() / max(df[col].notna().sum(), 1)

                if convert_ratio > 0.6:
                    df[col] = numeric
                    converted = int(numeric.notna().sum())
                    audit.append({
                        "action": "PARSE_CURRENCY", "column": col,
                        "detail": f"Stripped currency symbols and converted {converted} values to numeric",
                        "rows_affected": converted, "confidence": 95,
                        "source": "deterministic",
                    })
                    continue  # Skip further checks — column is now numeric

            # Step 3: Try general string-to-numeric conversion (commas as thousands)
            clean = df[col].dropna().astype(str)
            stripped = clean.str.replace(',', '', regex=False).str.strip()
            numeric = pd.to_numeric(stripped, errors='coerce')
            numeric_ratio = numeric.notna().sum() / max(len(clean), 1)

            if numeric_ratio > 0.7:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(',', '', regex=False).str.strip(),
                    errors='coerce'
                )
                converted = int(df[col].notna().sum())
                audit.append({
                    "action": "CONVERT_TO_NUMERIC", "column": col,
                    "detail": f"Converted {converted} string values to numeric type",
                    "rows_affected": converted, "confidence": 90,
                    "source": "deterministic",
                })

        return audit

    def get_status(self) -> dict:
        return {"engine": "CSVCorrector", "llm_available": self._llm.is_available,
                "rag_available": self._rag.is_ready,
                "auto_apply_threshold": self.AUTO_APPLY_THRESHOLD}
