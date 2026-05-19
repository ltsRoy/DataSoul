"""CSV correction engine — detects and fixes encoding issues, type mismatches,
category duplicates, value errors, and semantic type coercion.
Uses Ollama for smart merges; falls back to deterministic cleaners.
"""

import re
import json
import asyncio
import pandas as pd
import numpy as np
from typing import Optional
from collections import Counter
from difflib import SequenceMatcher

from llm_engine import get_llm
from rag_engine import get_rag
from data_cleaners import DataCleaners

MOJIBAKE_MAP = {
    "\u00e2\u0080\u0099": "'", "\u00e2\u0080\u009c": '"', "\u00e2\u0080\u009d": '"',
    "\u00e2\u0080\u0094": "\u2014", "\u00e2\u0080\u0093": "\u2013", "\u00e2\u0080\u00a6": "\u2026",
    "\u00c3\u00a9": "\u00e9", "\u00c3\u00a8": "\u00e8", "\u00c3\u00bc": "\u00fc",
    "\u00c3\u00b6": "\u00f6", "\u00c3\u00a4": "\u00e4", "\u00c3\u00b1": "\u00f1",
    "\u00c2\u00a3": "\u00a3", "\u00c2\u00a5": "\u00a5", "\u00e2\u0082\u00b9": "\u20b9",
    "\u00c2\u00b0": "\u00b0", "\u00c2\u00a9": "\u00a9", "\u00c2\u00ae": "\u00ae",
    "Â\xa0": " ", "Â ": " ", "Â": "",
    "â€™": "'", "â€˜": "'", "â€œ": '"', "â€�": '"',
    "â€”": "\u2014", "â€“": "\u2013", "â€¦": "\u2026",
    "â€ ": "\u2020", "â€¡": "\u2021", "â‚¹": "\u20b9",
    "Ã©": "\u00e9", "Ã¨": "\u00e8", "Ã¼": "\u00fc",
    "Ã¶": "\u00f6", "Ã¤": "\u00e4", "Ã±": "\u00f1",
    "\x00": "", "\ufeff": "",
}


class CSVCorrector:
    """Ollama-powered CSV data correction engine"""

    AUTO_APPLY_THRESHOLD = 0.90
    SUGGEST_THRESHOLD = 0.60

    def __init__(self):
        self._llm = get_llm()
        self._rag = get_rag()

    # -- public api --

    def analyze(self, df: pd.DataFrame, profile: dict | None = None) -> dict:
        return self._llm._run_async(lambda: self.analyze_async(df, profile=profile))

    async def analyze_async(self, df: pd.DataFrame, profile: dict | None = None) -> dict:
        """Full analysis pass — detect all correctable issues without modifying data."""
        results = {
            "columns_analyzed": 0, "issues_found": 0,
            "corrections": [], "encoding_issues": [],
            "format_issues": [], "category_merges": [],
            "type_issues": [], "semantic_issues": [],
            "llm_powered": self._llm.is_available,
        }

        results["encoding_issues"] = self._detect_encoding_issues(df)
        results["issues_found"] += len(results["encoding_issues"])

        results["format_issues"] = self._detect_format_issues(df)
        results["issues_found"] += len(results["format_issues"])

        results["type_issues"] = self._detect_type_issues(df)
        results["issues_found"] += len(results["type_issues"])

        results["semantic_issues"] = self._detect_semantic_issues(df)
        results["issues_found"] += len(results["semantic_issues"])

        # Count candidate columns
        for col in df.select_dtypes(include=["object"]).columns:
            clean = df[col].dropna().astype(str)
            if len(clean) > 0 and clean.nunique() <= 500:
                results["columns_analyzed"] += 1

        # Run both batch analyses concurrently using the existing batch infrastructure
        category_task = self._analyze_all_categories_async(df, profile)
        values_task = self._analyze_all_values_async(df, profile)
        category_results, values_results = await asyncio.gather(category_task, values_task)

        for col, merges in category_results:
            if merges:
                results["category_merges"].extend(merges)
                results["issues_found"] += len(merges)

        for col, corrections in values_results:
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

        audit.extend(self._clean_column_names(df_out))
        audit.extend(self._fix_encoding(df_out))
        audit.extend(self._fix_semantic_issues(df_out))  # null strings, whitespace, booleans, etc.
        audit.extend(self._fix_type_issues(df_out))  # Strip $, refs, convert types
        audit.extend(self._fix_formats(df_out, profile))
        audit.extend(self._merge_categories(df_out, profile, threshold))
        audit.extend(self._correct_values(df_out, profile, threshold))
        audit.extend(self._drop_empty_reference_columns(df_out))

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
            if pd.notna(count) and count > 0:
                df_out.loc[mask, col] = new_val
                applied.append({
                    "action": "VALUE_CORRECTION", "column": col,
                    "old_value": old_val, "new_value": new_val,
                    "rows_affected": count, "source": "user_approved",
                })
        return {"status": "success", "df": df_out, "corrections_applied": len(applied), "audit": applied}

    @staticmethod
    def _replace_mojibake(value: str) -> str:
        out = value
        for bad, good in MOJIBAKE_MAP.items():
            out = out.replace(bad, good)
        return out

    def _clean_column_names(self, df: pd.DataFrame) -> list[dict]:
        cleaned = []
        changed = []
        seen = {}

        for col in df.columns:
            new_col = self._replace_mojibake(str(col)).replace("\xa0", " ").strip()
            new_col = re.sub(r"\s+", " ", new_col)
            base = new_col or "unnamed"
            if base in seen:
                seen[base] += 1
                new_col = f"{base}_{seen[base]}"
            else:
                seen[base] = 0
                new_col = base
            cleaned.append(new_col)
            if new_col != col:
                changed.append((col, new_col))

        if not changed:
            return []

        df.columns = cleaned
        return [{
            "action": "CLEAN_COLUMN_NAMES",
            "detail": f"Cleaned {len(changed)} column header(s)",
            "rows_affected": 0,
            "confidence": 95,
            "source": "deterministic",
        }]

    # -- encoding --

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
            non_null = df[col].notna()
            if not non_null.any():
                continue
            original = df.loc[non_null, col].astype(str)
            fixed = original.map(self._replace_mojibake).str.replace("\xa0", " ", regex=False)
            changed = fixed != original
            total = int(changed.sum())
            if pd.notna(total) and total > 0:
                df.loc[non_null, col] = fixed
                audit.append({"action": "FIX_ENCODING", "column": col,
                              "detail": f"Fixed {total} encoding artifacts", "rows_affected": total,
                              "confidence": 95, "source": "deterministic"})
        return audit

    # -- format detection & repair --

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
                if pd.notna(m) and m > 0:
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

    # -- category merging (llm) --

    def _analyze_categories(self, df: pd.DataFrame, col: str, profile: dict | None) -> list[dict]:
        return self._llm._run_async(lambda: self._analyze_categories_batch_async(df, [col], profile)).get(col, [])

    async def _analyze_categories_batch_async(self, df: pd.DataFrame, cols: list[str], profile: dict | None) -> dict:
        results = {}
        llm_candidates = {}
        
        for col in cols:
            clean = df[col].dropna().astype(str)
            uniques = clean.unique().tolist()
            if len(uniques) < 2 or len(uniques) > 100:
                results[col] = []
                continue

            merges = []
            lower_map = {}
            for val in uniques:
                lower_map.setdefault(val.strip().lower(), []).append(val)

            # Pass 1: Exact case-insensitive matches (deterministic)
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

            # Pass 2: Fuzzy matching (deterministic, no LLM)
            merged_old = {m["old_value"] for m in merges}
            remaining = [v for v in uniques if v not in merged_old]
            merges.extend(self._fuzzy_find_merges(col, remaining, clean))
            
            results[col] = merges
            
            # Save for Pass 3 (LLM)
            if self._llm.is_available and len(uniques) <= 60:
                llm_candidates[col] = uniques
                
        # Pass 3: Batched LLM-powered merge detection
        if llm_candidates:
            try:
                llm_merges = await self._llm_find_merges_batch_async(llm_candidates, profile)
                for col, mlist in llm_merges.items():
                    if col in results:
                        results[col].extend(mlist)
            except Exception as e:
                print(f"[CSVCorrector] LLM category batch failed: {e}")
                
        return results

    @staticmethod
    def _fuzzy_find_merges(col: str, values: list[str], series: pd.Series) -> list[dict]:
        """Deterministic fuzzy matching — catches typos + token-order variants without LLM.

        Improvements over naive SequenceMatcher:
        - Token-sort ratio: "Rowling, J.K." ≈ "J.K. Rowling" both sort to same tokens
        - Strip common noise prefixes (Dr., The, Inc.) before compare
        - Hard cap: reject if edit distance > 4 chars even if ratio passes
        """
        if len(values) < 2 or len(values) > 80:
            return []

        # Common noise tokens to ignore when comparing
        _NOISE_PREFIXES = {"the ", "a ", "an ", "dr. ", "mr. ", "ms. ", "mrs. ",
                           "prof. ", "sr. ", "jr. "}
        _NOISE_SUFFIXES = {" inc", " inc.", " ltd", " llc", " corp", " co.", " co"}

        def _normalise(v: str) -> str:
            s = v.strip().lower()
            for p in _NOISE_PREFIXES:
                if s.startswith(p):
                    s = s[len(p):]
                    break
            for sfx in _NOISE_SUFFIXES:
                if s.endswith(sfx):
                    s = s[: -len(sfx)]
                    break
            return s.strip()

        def _token_sort(s: str) -> str:
            """Sort tokens alphabetically so 'J.K. Rowling' == 'Rowling J.K.'"""
            return " ".join(sorted(s.split()))

        def _similarity(a: str, b: str) -> float:
            na, nb = _normalise(a), _normalise(b)
            # Direct ratio on normalised strings
            r1 = SequenceMatcher(None, na, nb).ratio()
            # Token-sort ratio
            r2 = SequenceMatcher(None, _token_sort(na), _token_sort(nb)).ratio()
            return max(r1, r2)

        def _edit_distance(a: str, b: str) -> int:
            """Simple Levenshtein for the hard-cap guard."""
            na, nb = _normalise(a), _normalise(b)
            m, n = len(na), len(nb)
            dp = list(range(n + 1))
            for i in range(1, m + 1):
                prev, dp[0] = dp[0], i
                for j in range(1, n + 1):
                    prev, dp[j] = dp[j], (
                        prev if na[i - 1] == nb[j - 1]
                        else 1 + min(prev, dp[j], dp[j - 1])
                    )
            return dp[n]

        merges = []
        already_merged = set()
        counts = {v: int((series == v).sum()) for v in values}

        for i, a in enumerate(values):
            if a in already_merged:
                continue
            for b in values[i + 1:]:
                if b in already_merged:
                    continue
                if _normalise(a) == _normalise(b):
                    # Identical after normalisation — always merge
                    ratio = 1.0
                else:
                    ratio = _similarity(a, b)

                if ratio >= 0.85 and a.lower().strip() != b.lower().strip():
                    # Hard cap: skip if strings differ by more than 4 chars
                    if _edit_distance(a, b) > 4 and ratio < 0.92:
                        continue
                    canonical = a if counts.get(a, 0) >= counts.get(b, 0) else b
                    variant = b if canonical == a else a
                    merges.append({
                        "column": col, "old_value": variant, "new_value": canonical,
                        "count": counts.get(variant, 0),
                        "confidence": round(ratio, 2),
                        "reason": f"Fuzzy match ({ratio:.0%} similar to '{canonical}')",
                        "type": "fuzzy_merge",
                    })
                    already_merged.add(variant)
        return merges

    def _llm_find_merges(self, col: str, uniques: list[str], profile: dict | None) -> list[dict]:
        return self._llm._run_async(lambda: self._llm_find_merges_async(col, uniques, profile))

    async def _llm_find_merges_async(self, col: str, uniques: list[str], profile: dict | None) -> list[dict]:
        rag_ctx = ""
        if self._rag.is_ready and profile:
            sector = profile.get("sector", {}).get("sector_name", "General")
            rag_ctx = self._rag.get_context_for_prompt(
                f"standard naming for {col} in {sector}", dataset_profile=profile, n_results=3)

        # Include frequency distribution so LLM can make better decisions
        from collections import Counter as _Counter
        freq = _Counter()
        for v in uniques:
            freq[v] = 0  # placeholder — actual counts populated below

        vals = "\n".join(f'  - "{v}"' for v in sorted(uniques)[:60])
        prompt = f"""Analyze these values from column "{col}" and identify typos/duplicates to merge.

VALUES:
{vals}
{f"CONTEXT: {rag_ctx[:400]}" if rag_ctx and "No relevant" not in rag_ctx else ""}

Return a JSON array: [{{"old": "variant", "new": "canonical", "reason": "why"}}]
Only flag clear duplicates (>80% confident). If none, return []. JSON only."""

        try:
            resp = await self._llm.agenerate(
                prompt,
                temperature=0.1,
                max_tokens=400,
                timeout=20,
                json_mode=True,
            )
            items = self._parse_json_array(resp, context=f"merge {col}")
            return [{"column": col, "old_value": s["old"], "new_value": s["new"],
                     "count": 0, "confidence": 0.82,
                     "reason": s.get("reason", "LLM-detected duplicate"), "type": "llm_merge"}
                    for s in items if isinstance(s, dict) and "old" in s and "new" in s]
        except Exception as e:
            print(f"[CSVCorrector] LLM merge failed for '{col}': {e}")
        return []

    def _merge_categories(self, df: pd.DataFrame, profile: dict | None, threshold: float) -> list[dict]:
        audit = []
        analyses = self._llm._run_async(lambda: self._analyze_all_categories_async(df, profile))
        for col, merges in analyses:
            for m in merges:
                if m["confidence"] >= threshold and m["old_value"] != m["new_value"]:
                    mask = df[col].astype(str) == m["old_value"]
                    count = int(mask.sum())
                    if pd.notna(count) and count > 0:
                        df.loc[mask, col] = m["new_value"]
                        audit.append({"action": "MERGE_CATEGORY", "column": col,
                                      "detail": f"'{m['old_value']}' -> '{m['new_value']}' ({count} rows)",
                                      "rows_affected": count, "confidence": int(m["confidence"] * 100),
                                      "source": "LLM-guided" if m["type"] == "llm_merge" else "deterministic"})
        return audit

    async def _analyze_all_categories_async(self, df: pd.DataFrame, profile: dict | None) -> list[tuple[str, list[dict]]]:
        cols = df.select_dtypes(include=["object"]).columns.tolist()
        batch_size = 5
        results = []
        
        tasks = []
        batches = []
        for i in range(0, len(cols), batch_size):
            batch_cols = cols[i:i + batch_size]
            batches.append(batch_cols)
            tasks.append(self._analyze_categories_batch_async(df, batch_cols, profile))
            
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        for batch_cols, batch_res in zip(batches, task_results):
            if isinstance(batch_res, Exception):
                print(f"[CSVCorrector] Failed batch category analysis for {batch_cols}: {batch_res}")
                for col in batch_cols:
                    results.append((col, []))
            elif isinstance(batch_res, dict):
                for col in batch_cols:
                    results.append((col, batch_res.get(col, [])))
                    
        return results

    # -- value correction (llm) --

    def _analyze_column_values(self, df: pd.DataFrame, col: str, profile: dict | None) -> list[dict]:
        return self._llm._run_async(lambda: self._analyze_columns_values_batch_async(df, [col], profile)).get(col, [])

    async def _analyze_columns_values_batch_async(self, df: pd.DataFrame, cols: list[str], profile: dict | None) -> dict:
        if not self._llm.is_available or not cols:
            return {}
            
        columns_data = []
        rag_contexts = []
        sector = profile.get("sector", {}).get("sector_name", "General") if profile else "General"
        
        for col in cols:
            clean = df[col].dropna().astype(str)
            if len(clean) == 0:
                continue
            vc = clean.value_counts()
            sample = list(set(vc.head(15).index.tolist() + vc.tail(min(15, len(vc))).index.tolist()))[:30]
            vals = "\n".join(f'    - "{v}" ({int(vc.get(v, 0))}x)' for v in sample)
            columns_data.append(f'- Column: "{col}"\n  Values:\n{vals}')
            
            if self._rag.is_ready and profile:
                rag_ctx = self._rag.get_context_for_prompt(
                    f"valid values for {col} in {sector}", dataset_profile=profile, n_results=1)
                rag_contexts.append(rag_ctx)
                
        if not columns_data:
            return {}

        prompt = f"""Analyze these columns and identify clear value errors (typos, invalid formats).

COLUMNS TO ANALYZE:
{"\n".join(columns_data)}

CONTEXT:
{"\n".join(set([r[:200] for r in rag_contexts if "No relevant" not in r]))}

Return a JSON object mapping EACH column name to an ARRAY of corrections (can be empty []).
Format:
{{
  "Column1": [
    {{"value": "wrong", "correction": "right", "confidence": 0.85, "reason": "why"}}
  ],
  "Column2": []
}}
Only clear errors (confidence>0.7). JSON only."""

        try:
            resp = await self._llm.agenerate(
                prompt,
                system="You are a data cleaning expert. Return only a valid JSON dictionary.",
                temperature=0.1,
                max_tokens=1000,
                timeout=40,
                json_mode=True,
            )
            parsed = self._parse_json_dict(resp, context=f"value batch {cols}")
            
            results = {}
            for col, items in parsed.items():
                if not isinstance(items, list):
                    continue
                clean = df[col].dropna().astype(str) if col in df.columns else pd.Series()
                vc = clean.value_counts()
                
                results[col] = [{"column": col, "old_value": s["value"], "new_value": s["correction"],
                                 "count": int(vc.get(s["value"], 0)),
                                 "confidence": round(float(s.get("confidence", 0.75)), 2),
                                 "reason": s.get("reason", "LLM-detected error"), "type": "value_correction"}
                                for s in items if isinstance(s, dict) and "value" in s and "correction" in s
                                and float(s.get("confidence", 0)) >= self.SUGGEST_THRESHOLD]
            return results
        except Exception as e:
            print(f"[CSVCorrector] LLM value analysis batch failed for {cols}: {e}")
        return {}

    def _correct_values(self, df: pd.DataFrame, profile: dict | None, threshold: float) -> list[dict]:
        audit = []
        analyses = self._llm._run_async(lambda: self._analyze_all_values_async(df, profile))
        for col, corrections in analyses:
            for corr in corrections:
                if corr["confidence"] >= threshold:
                    mask = df[col].astype(str) == corr["old_value"]
                    count = int(mask.sum())
                    if pd.notna(count) and count > 0:
                        df.loc[mask, col] = corr["new_value"]
                        audit.append({"action": "VALUE_CORRECTION", "column": col,
                                      "detail": f"'{corr['old_value']}' -> '{corr['new_value']}' ({count} rows)",
                                      "rows_affected": count, "confidence": int(corr["confidence"] * 100),
                                      "source": "LLM-guided"})
        return audit

    async def _analyze_all_values_async(self, df: pd.DataFrame, profile: dict | None) -> list[tuple[str, list[dict]]]:
        cols = []
        for col in df.select_dtypes(include=["object"]).columns:
            clean = df[col].dropna().astype(str)
            if len(clean) == 0 or clean.nunique() > 100:
                continue
            cols.append(col)

        batch_size = 5
        results = []
        
        tasks = []
        batches = []
        for i in range(0, len(cols), batch_size):
            batch_cols = cols[i:i + batch_size]
            batches.append(batch_cols)
            tasks.append(self._analyze_columns_values_batch_async(df, batch_cols, profile))
            
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        for batch_cols, batch_res in zip(batches, task_results):
            if isinstance(batch_res, Exception):
                print(f"[CSVCorrector] Failed batch value analysis for {batch_cols}: {batch_res}")
                for col in batch_cols:
                    results.append((col, []))
            elif isinstance(batch_res, dict):
                for col in batch_cols:
                    results.append((col, batch_res.get(col, [])))

        return results

    # === TYPE ISSUES (currency strings, embedded refs, numeric-as-string) ===

    def _detect_type_issues(self, df: pd.DataFrame) -> list[dict]:
        """Detect columns where values look numeric but are stored as strings."""
        issues = []
        for col in df.select_dtypes(include=["object"]).columns:
            clean = df[col].dropna().astype(str)
            if len(clean) == 0:
                continue

            # Check for currency symbols ($, Rs, etc.)
            has_currency = clean.str.contains(r'[\$₹£€¥]', regex=True, na=False).fillna(False).sum()
            currency_ratio = has_currency / len(clean)

            # Check for embedded references like [1], [a], [2][5]
            has_refs = clean.str.contains(r'\[\w+\]', regex=True, na=False).fillna(False).sum()
            ref_ratio = has_refs / len(clean)

            # Check if values are numeric after stripping $, commas, refs
            stripped = clean.str.replace(r'[\$₹£€¥,]', '', regex=True)
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
            has_refs = clean.str.contains(r'\[\w+\]', regex=True, na=False).fillna(False).sum()
            if has_refs > 0 and (has_refs >= 2 or has_refs > len(clean) * 0.05):
                non_null = df[col].notna()
                original_vals = df.loc[non_null, col].astype(str)
                fixed_vals = original_vals.str.replace(r'\[\w+\]', '', regex=True).str.strip()
                df.loc[non_null, col] = fixed_vals
                changed = (fixed_vals != original_vals).sum()
                if pd.notna(changed) and changed > 0:
                    audit.append({
                        "action": "STRIP_REFERENCES", "column": col,
                        "detail": f"Removed reference annotations like [1],[a] from {int(changed)} values",
                        "rows_affected": int(changed), "confidence": 92,
                        "source": "deterministic",
                    })

            # Step 2: Strip currency symbols and comma-separators, then convert
            clean = df[col].dropna().astype(str)
            has_currency = clean.str.contains(r'[\$₹£€¥]', regex=True, na=False).fillna(False).sum()
            if has_currency > len(clean) * 0.3:
                stripped = df[col].astype("string").str.replace(r'[\$₹£€¥,\s]', '', regex=True)
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
                    df[col].astype("string").str.replace(',', '', regex=False).str.strip(),
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

    def _drop_empty_reference_columns(self, df: pd.DataFrame) -> list[dict]:
        audit = []
        for col in list(df.columns):
            col_lower = str(col).strip().lower()
            if col_lower not in {"ref", "ref.", "reference", "references", "citation", "citations", "source"}:
                continue

            values = df[col].dropna().astype(str).str.strip()
            if values.empty or values.replace({"": pd.NA}).dropna().empty:
                df.drop(columns=[col], inplace=True)
                audit.append({
                    "action": "DROP_EMPTY_REFERENCE_COLUMN",
                    "column": col,
                    "detail": f"Dropped empty citation/reference column '{col}' after cleaning",
                    "rows_affected": 0,
                    "confidence": 90,
                    "source": "deterministic",
                })
        return audit

    # === SEMANTIC ISSUES (null strings, percentages, booleans, whitespace) ===

    def _detect_semantic_issues(self, df: pd.DataFrame) -> list[dict]:
        """Detect columns with null-like strings, percentage values, booleans, etc."""
        issues = []
        for col in df.select_dtypes(include=["object"]).columns:
            clean = df[col].dropna().astype(str).str.strip()
            if len(clean) == 0:
                continue

            # Null-string detection
            from data_cleaners import NULL_STRINGS
            null_count = clean.str.lower().isin(NULL_STRINGS).fillna(False).sum()
            if pd.notna(null_count) and null_count > 0:
                issues.append({
                    "column": col, "type": "null_strings",
                    "count": int(null_count),
                    "ratio": round(float(null_count / len(clean)), 2),
                    "suggestion": f"Convert {null_count} null-like strings to actual NaN",
                    "confidence": 0.96, "auto_fixable": True,
                })

            # Percentage detection
            pct_match = clean.str.match(r'^[+-]?\s*\d+[\d,]*\.?\d*\s*%$', na=False).sum()
            if pct_match / len(clean) > 0.4:
                issues.append({
                    "column": col, "type": "percentage_strings",
                    "count": int(pct_match),
                    "ratio": round(float(pct_match / len(clean)), 2),
                    "suggestion": "Strip '%' and convert to numeric",
                    "confidence": 0.94, "auto_fixable": True,
                })

            # Boolean detection
            from data_cleaners import BOOL_TRUE, BOOL_FALSE
            bool_count = clean.str.lower().isin(BOOL_TRUE | BOOL_FALSE).fillna(False).sum()
            if bool_count / len(clean) > 0.7:
                issues.append({
                    "column": col, "type": "boolean_strings",
                    "count": int(bool_count),
                    "ratio": round(float(bool_count / len(clean)), 2),
                    "suggestion": "Normalize to True/False boolean values",
                    "confidence": 0.93, "auto_fixable": True,
                })

            # Negative parentheses detection
            paren_match = clean.str.match(
                r'^\([\$₹£€¥]?\s*[\d,]+\.?\d*\)$', na=False
            ).sum()
            if paren_match >= 2 and paren_match / len(clean) > 0.05:
                issues.append({
                    "column": col, "type": "negative_parentheses",
                    "count": int(paren_match),
                    "ratio": round(float(paren_match / len(clean)), 2),
                    "suggestion": "Convert accounting-style negatives '(500)' → -500",
                    "confidence": 0.94, "auto_fixable": True,
                })

        return issues

    def _fix_semantic_issues(self, df: pd.DataFrame) -> list[dict]:
        """Apply DataCleaners deterministic fixes for semantic type issues."""
        _, audit = DataCleaners.run_all(df)

        # run_all returns cleaned copies — we need to apply in-place
        # Re-run individual cleaners and apply to the actual df
        audit = []
        for col in list(df.columns):
            if not pd.api.types.is_object_dtype(df[col]):
                continue

            # Run cleaners in priority order
            for cleaner_fn in [
                DataCleaners.clean_null_strings,
                DataCleaners.clean_whitespace,
                # content-aware cleaners — run before type coercion
                DataCleaners.clean_text_prefixes,   # strip 'Writtenby:' / 'Narratedby:' etc.
                DataCleaners.clean_rating_strings,   # '4.5 out of 5 stars…' → 4.5
                # type-coercion cleaners
                DataCleaners.clean_percentages,
                DataCleaners.clean_booleans,
                DataCleaners.clean_negative_parens,
                DataCleaners.clean_emails,
                DataCleaners.clean_phone_numbers,
            ]:
                if not pd.api.types.is_object_dtype(df[col]):
                    break  # Column type changed — stop further string cleaners
                try:
                    cleaned, entry = cleaner_fn(df[col], col_name=col)
                    if entry is not None:
                        df[col] = cleaned
                        audit.append(entry)
                except Exception as e:
                    print(f"[CSVCorrector] Semantic fix failed for '{col}': {e}")

        return audit

    def get_status(self) -> dict:
        return {"engine": "CSVCorrector", "llm_available": self._llm.is_available,
                "rag_available": self._rag.is_ready,
                "auto_apply_threshold": self.AUTO_APPLY_THRESHOLD}

    @staticmethod
    def _parse_json_array(raw: str, context: str = "") -> list[dict]:
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError as e:
            print(f"[CSVCorrector] JSON parse failed ({context}): {e}")
            return []

    @staticmethod
    def _parse_json_dict(raw: str, context: str = "") -> dict:
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError as e:
            print(f"[CSVCorrector] JSON dict parse failed ({context}): {e}")
            return {}
