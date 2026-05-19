"""LLM-Powered Cleaning Layer — DataSoul AI Engine

The LLM does the *discovery* work:
  - Inspect sample values per column
  - Identify dirty patterns (prefixes, junk suffixes, unit strings, encoding noise, etc.)
  - Return a structured JSON cleaning plan

Python then *executes* each plan deterministically at scale (no LLM per-row).
This is the correct architecture: LLM for intelligence, code for execution.
"""

import re
import json
import asyncio
import pandas as pd
import numpy as np
from typing import Optional

from rag_engine import get_rag


# ─── Prompt Templates ────────────────────────────────────────────────────────

_BATCH_COLUMN_ANALYSIS_PROMPT = """\
You are a precise data cleaning expert. Analyze the sample values from these CSV columns and \
identify ALL dirty patterns that need cleaning for EACH column.

COLUMNS TO ANALYZE:
{columns_data}

RETRIEVED DATASOUL CLEANING RULES:
{rag_context}

KNOWN DIRTY PATTERNS TO LOOK FOR:
- Unit suffixes and conversions: "8GB", "1.37kg", "2.5GHz", "4.5 hrs", "120 min" (Strip text, leave number)
- Label prefixes: "Writtenby:", "Narratedby:", "Author:", "Publisher:"
- Rating strings: "4.5 out of 5 stars"
- Currency strings: "₹1,256.00", "$45.99"
- Comma-formatted numbers stored as strings: "1,234.56"
- Mixed case issues (all-caps names, inconsistent casing)
- Duplicate words: "English English", "Fiction Fiction"
- Encoding artifacts: â€™, Ã©, etc.
- Boolean strings: "Yes/No", "TRUE/FALSE"
- Null-like strings: "N/A", "None", "null"

For each issue found, return a JSON object describing the fix.
Return a strict JSON object mapping EACH column name to an ARRAY of issue objects (can be empty []).

Format your output exactly like this:
{{
  "Column1": [
    {{
      "issue": "short_name",
      "description": "what the problem is",
      "fix_type": "strip_prefix|strip_suffix|extract_number|regex_replace|map_values|to_numeric|to_boolean|to_null|normalise_case|deduplicate_words",
      "confidence": 0.9,
      "prefix_patterns": ["list"] // or "suffix_pattern", "extract_regex", "strip_chars" depending on fix_type
    }}
  ],
  "Column2": []
}}

IMPORTANT:
- confidence >= 0.80 means auto-apply; lower = suggest only
- If the column looks clean, return []
- Return ONLY valid JSON mapping column names to arrays.
"""

_BATCH_SCHEMA_PROMPT = """\
You are a data schema expert. Given these column names and sample values from a CSV, \
identify the semantic type of each column so cleaning rules can be applied correctly.

COLUMNS:
{col_summaries}

For each column, return a JSON object with:
- "column": column name
- "semantic_type": one of [
    "person_name", "book_title", "product_name", "description",
    "author", "narrator", "publisher",
    "price", "currency", "cost",
    "rating", "score", "review_count",
    "duration", "time", "date",
    "language", "country", "region",
    "category", "genre", "tag",
    "url", "email", "phone",
    "boolean", "id", "free_text", "unknown"
  ]
- "cleaning_hints": list of 1-3 short strings describing obvious issues

Return a JSON array, one object per column. JSON only.
"""


class LLMCleaner:
    """LLM-powered discovery + Python execution for data cleaning.

    Usage:
        cleaner = LLMCleaner(llm)
        plans, audit = cleaner.clean(df, min_confidence=0.80)
    """

    def __init__(self, llm):
        self._llm = llm
        self._rag = get_rag()
        self._max_concurrency = 3

    @property
    def is_available(self) -> bool:
        return self._llm is not None and self._llm.is_available

    # ─── Public API ─────────────────────────────────────────────────────────

    def clean(self, df: pd.DataFrame,
              min_confidence: float = 0.75) -> tuple[pd.DataFrame, list[dict]]:
        """Run LLM-powered cleaning on all columns.

        Returns (cleaned_df, audit_trail).
        """
        if not self.is_available:
            return df, []
        return self._llm._run_async(lambda: self.clean_async(df, min_confidence=min_confidence))

    async def clean_async(self, df: pd.DataFrame,
                          min_confidence: float = 0.75) -> tuple[pd.DataFrame, list[dict]]:
        """Async LLM-powered cleaning with batched column discovery."""
        if not self.is_available:
            return df, []

        df_out = df.copy()
        audit = []

        # Step 1: Get schema/semantic types for smarter prompting
        schema = await self._infer_schema_async(df_out)

        # Step 2: Analyse columns in batches to reduce local Ollama latency
        cols = df_out.columns.tolist()
        batch_size = 5
        all_plans = {}

        for i in range(0, len(cols), batch_size):
            batch_cols = cols[i:i + batch_size]
            try:
                batch_plans = await self._analyse_columns_batch_async(df_out, batch_cols, schema)
                all_plans.update(batch_plans)
            except Exception as e:
                print(f"[LLMCleaner] Failed batch analysis for columns {batch_cols}: {e}")

        # Step 3: Apply plans
        for col, plans in all_plans.items():
            if col not in df_out.columns:
                continue
            try:
                for plan in plans:
                    if plan.get("confidence", 0) < min_confidence:
                        continue
                    entry = self._apply_plan(df_out, col, plan)
                    if entry:
                        audit.append(entry)
            except Exception as e:
                print(f"[LLMCleaner] Failed applying plan for '{col}': {e}")

        return df_out, audit

    # ─── Column Analysis ────────────────────────────────────────────────────

    def _analyse_column(self, series: pd.Series, col_name: str,
                        schema_hint: dict) -> list[dict]:
        # Sync wrapper fallback if ever needed for single column
        return self._llm._run_async(
            lambda: self._analyse_columns_batch_async(series.to_frame(), [col_name], {col_name: schema_hint})
        ).get(col_name, [])

    async def _analyse_columns_batch_async(self, df: pd.DataFrame, cols: list[str],
                                           schema_hints: dict) -> dict:
        """Ask the LLM to identify dirty patterns for multiple columns in one prompt."""
        if not cols:
            return {}

        columns_data = []
        rag_contexts = []
        
        for col in cols:
            series = df[col]
            non_null = series.dropna()
            if len(non_null) == 0:
                continue
                
            vc = non_null.astype(str).value_counts()
            head_samples = vc.head(10).index.tolist()
            tail_samples = []
            if len(vc) > 10:
                remaining = vc.tail(len(vc) - 10)
                n_samples = min(5, len(remaining))
                if n_samples > 0:
                    tail_samples = remaining.sample(n=n_samples, random_state=42).index.tolist()
            samples = head_samples + tail_samples
            
            sample_block = "\n".join(
                f'    - {repr(v).replace(chr(92), chr(92)+chr(92))}  (\u00d7{int(vc[v])})'
                for v in samples
            )
            
            schema_hint = schema_hints.get(col, {})
            dtype_str = str(series.dtype)
            if schema_hint.get("semantic_type"):
                dtype_str += f" / semantic: {schema_hint['semantic_type']}"
                
            columns_data.append(f'- Column: "{col}"\n  Type: {dtype_str}\n  Samples:\n{sample_block}')
            rag_contexts.append(self._get_column_rag_context(col, schema_hint))
        
        if not columns_data:
            return {}

        prompt = _BATCH_COLUMN_ANALYSIS_PROMPT.format(
            columns_data="\n".join(columns_data),
            rag_context="\n".join(set([r for r in rag_contexts if "No relevant" not in r]))
        )

        raw = await self._llm.agenerate(
            prompt,
            system="You are a precise data engineering expert. Return only valid JSON dictionaries.",
            temperature=0.05,
            max_tokens=1500,
            timeout=40,  # Elevated timeout for batched response
            json_mode=True,
        )

        return self._parse_json_dict(raw, context=f"batch columns {cols}")

    def _infer_schema(self, df: pd.DataFrame) -> dict:
        return self._llm._run_async(lambda: self._infer_schema_async(df))

    async def _infer_schema_async(self, df: pd.DataFrame) -> dict:
        """Batch-infer semantic types for all columns via a single LLM call."""
        if not self.is_available or len(df.columns) == 0:
            return {}

        summaries = []
        for col in df.columns[:20]:  # cap at 20 cols per call
            sample = df[col].dropna().astype(str).head(5).tolist()
            summaries.append(f'- "{col}": {sample}')

        prompt = _BATCH_SCHEMA_PROMPT.format(
            col_summaries="\n".join(summaries)
        )

        raw = await self._llm.agenerate(
            prompt,
            system="Return only valid JSON.",
            temperature=0.05,
            max_tokens=600,
            timeout=15,
            json_mode=True,
        )

        items = self._parse_json_array(raw, context="schema inference")
        return {
            item["column"]: item
            for item in items
            if isinstance(item, dict) and "column" in item
        }

    # ─── Plan Execution ─────────────────────────────────────────────────────

    def _apply_plan(self, df: pd.DataFrame, col: str, plan: dict) -> dict | None:
        """Execute one cleaning plan on df[col] in-place. Returns audit entry or None."""
        fix_type = plan.get("fix_type", "")
        confidence = plan.get("confidence", 0)
        issue = plan.get("issue", fix_type)
        desc = plan.get("description", "")

        try:
            if fix_type == "strip_prefix":
                return self._fix_strip_prefix(df, col, plan, confidence, issue, desc)

            elif fix_type == "strip_suffix":
                return self._fix_strip_suffix(df, col, plan, confidence, issue, desc)

            elif fix_type == "extract_number":
                return self._fix_extract_number(df, col, plan, confidence, issue, desc)

            elif fix_type == "to_numeric":
                return self._fix_to_numeric(df, col, plan, confidence, issue, desc)

            elif fix_type == "to_null":
                return self._fix_to_null(df, col, plan, confidence, issue, desc)

            elif fix_type == "regex_replace":
                return self._fix_regex_replace(df, col, plan, confidence, issue, desc)

            elif fix_type == "map_values":
                return self._fix_map_values(df, col, plan, confidence, issue, desc)

            elif fix_type == "to_boolean":
                return self._fix_to_boolean(df, col, plan, confidence, issue, desc)

            elif fix_type == "normalise_case":
                return self._fix_normalise_case(df, col, plan, confidence, issue, desc)

            elif fix_type == "deduplicate_words":
                return self._fix_deduplicate_words(df, col, plan, confidence, issue, desc)

        except Exception as e:
            print(f"[LLMCleaner] apply_plan failed ({fix_type}) for '{col}': {e}")

        return None

    # ─── Fix Implementations ────────────────────────────────────────────────

    @staticmethod
    def _fix_strip_prefix(df, col, plan, conf, issue, desc):
        prefixes = [p.lower() for p in plan.get("prefix_patterns", [])]
        if not prefixes:
            return None

        non_null = df[col].notna()
        original = df.loc[non_null, col].astype(str)

        def strip(v):
            low = v.strip().lower()
            for p in prefixes:
                if low.startswith(p):
                    return v.strip()[len(p):].strip()
            return v.strip()

        cleaned = original.apply(strip)
        changed = (cleaned != original).sum()
        if changed == 0:
            return None
        df.loc[non_null, col] = cleaned
        return _audit(col, "LLM_STRIP_PREFIX", issue, desc, int(changed), conf)

    @staticmethod
    def _fix_strip_suffix(df, col, plan, conf, issue, desc):
        pattern = plan.get("suffix_pattern", "")
        if not pattern:
            return None

        non_null = df[col].notna()
        original = df.loc[non_null, col].astype(str)
        cleaned = original.str.replace(pattern, "", regex=True).str.strip()
        changed = (cleaned != original).sum()
        if changed == 0:
            return None
        df.loc[non_null, col] = cleaned
        return _audit(col, "LLM_STRIP_SUFFIX", issue, desc, int(changed), conf)

    @staticmethod
    def _fix_extract_number(df, col, plan, conf, issue, desc):
        pattern = plan.get("extract_regex", "")
        if not pattern:
            return None

        try:
            rx = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return None

        if not pd.api.types.is_object_dtype(df[col]):
            return None

        non_null = df[col].notna()
        original = df.loc[non_null, col].astype(str)

        def extract(v):
            m = rx.search(v)
            return m.group(1) if m else v

        extracted = original.apply(extract)
        
        # We test if the extracted values are actually numeric
        numeric_test = pd.to_numeric(extracted, errors="coerce")
        changed_mask = (extracted != original) & numeric_test.notna()
        changed = changed_mask.sum()
        
        if changed == 0:
            return None

        # Only apply changes where extraction succeeded AND was numeric
        result = original.copy()
        result[changed_mask] = numeric_test[changed_mask]
        df.loc[non_null, col] = result
        
        # Try to cast the entire column if mostly numeric now
        num_ratio = pd.to_numeric(df[col], errors="coerce").notna().sum() / max(df[col].notna().sum(), 1)
        if num_ratio > 0.8:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            
        return _audit(col, "LLM_EXTRACT_NUMBER", issue, desc, int(changed), conf)

    @staticmethod
    def _fix_to_numeric(df, col, plan, conf, issue, desc):
        strip_chars = plan.get("strip_chars", ",₹$£€¥ ")
        non_null = df[col].notna()
        original = df.loc[non_null, col].astype(str)

        pattern = "[" + re.escape(strip_chars) + "]"
        cleaned_str = original.str.replace(pattern, "", regex=True).str.strip()
        numeric = pd.to_numeric(cleaned_str, errors="coerce")
        changed = numeric.notna().sum()
        if changed < non_null.sum() * 0.5:
            return None  # less than 50% convertible — skip

        result = df[col].copy().astype(object)
        result[non_null] = numeric
        df[col] = pd.to_numeric(result, errors="coerce")
        return _audit(col, "LLM_TO_NUMERIC", issue, desc, int(changed), conf)

    @staticmethod
    def _fix_to_null(df, col, plan, conf, issue, desc):
        null_strings = {s.lower() for s in plan.get("null_strings", [])}
        if not null_strings:
            return None

        non_null = df[col].notna()
        original = df.loc[non_null, col].astype(str)
        is_null_str = original.str.strip().str.lower().isin(null_strings)
        count = int(is_null_str.sum())
        if count == 0:
            return None

        df.loc[original[is_null_str].index, col] = np.nan
        return _audit(col, "LLM_TO_NULL", issue, desc, count, conf)

    @staticmethod
    def _fix_regex_replace(df, col, plan, conf, issue, desc):
        find = plan.get("find", "")
        replace = plan.get("replace", "")
        if not find:
            return None

        try:
            rx = re.compile(find, re.IGNORECASE)
        except re.error:
            return None

        non_null = df[col].notna()
        original = df.loc[non_null, col].astype(str)
        cleaned = original.str.replace(rx, replace, regex=True).str.strip()
        # Fallback to original if regex wiped it out completely (when it shouldn't have)
        cleaned = cleaned.replace("", np.nan).fillna(original)
        
        changed = (cleaned != original).sum()
        if changed == 0:
            return None
        df.loc[non_null, col] = cleaned
        return _audit(col, "LLM_REGEX_REPLACE", issue, desc, int(changed), conf)

    @staticmethod
    def _fix_map_values(df, col, plan, conf, issue, desc):
        mapping = plan.get("mapping", {})
        if not mapping:
            return None

        non_null = df[col].notna()
        original = df.loc[non_null, col].astype(str)
        # Case-insensitive lookup
        lower_map = {k.lower(): v for k, v in mapping.items()}
        cleaned = original.apply(
            lambda v: lower_map.get(v.strip().lower(), v)
        )
        changed = (cleaned != original).sum()
        if changed == 0:
            return None
        df.loc[non_null, col] = cleaned
        return _audit(col, "LLM_MAP_VALUES", issue, desc, int(changed), conf)

    @staticmethod
    def _fix_to_boolean(df, col, plan, conf, issue, desc):
        true_vals = {v.lower() for v in plan.get("true_values", [])}
        false_vals = {v.lower() for v in plan.get("false_values", [])}
        if not true_vals and not false_vals:
            return None

        non_null = df[col].notna()
        original = df.loc[non_null, col].astype(str).str.strip().str.lower()
        all_known = true_vals | false_vals
        known_ratio = original.isin(all_known).sum() / max(len(original), 1)
        if known_ratio < 0.7:
            return None

        result = original.map(
            lambda v: True if v in true_vals else (False if v in false_vals else np.nan)
        )
        count = int(result.notna().sum())
        if count == 0:
            return None
        df.loc[non_null, col] = result
        return _audit(col, "LLM_TO_BOOLEAN", issue, desc, count, conf)

    @staticmethod
    def _fix_normalise_case(df, col, plan, conf, issue, desc):
        style = plan.get("case_style", "title")
        non_null = df[col].notna()
        if not pd.api.types.is_object_dtype(df[col]):
            return None
        original = df.loc[non_null, col].astype(str)
        if style == "title":
            cleaned = original.str.strip().str.title()
        elif style == "lower":
            cleaned = original.str.strip().str.lower()
        elif style == "upper":
            cleaned = original.str.strip().str.upper()
        else:
            return None
        changed = (cleaned != original).sum()
        if changed == 0:
            return None
        df.loc[non_null, col] = cleaned
        return _audit(col, "LLM_NORMALISE_CASE", issue, desc, int(changed), conf)

    @staticmethod
    def _fix_deduplicate_words(df, col, plan, conf, issue, desc):
        non_null = df[col].notna()
        if not pd.api.types.is_object_dtype(df[col]):
            return None
        original = df.loc[non_null, col].astype(str)

        def dedup_words(v: str) -> str:
            words = v.split()
            seen = []
            for w in words:
                if not seen or w.lower() != seen[-1].lower():
                    seen.append(w)
            return " ".join(seen)

        cleaned = original.apply(dedup_words)
        changed = (cleaned != original).sum()
        if changed == 0:
            return None
        df.loc[non_null, col] = cleaned
        return _audit(col, "LLM_DEDUP_WORDS", issue, desc, int(changed), conf)

    # ─── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json_array(raw: str, context: str = "") -> list[dict]:
        """Parse a strict top-level JSON array from LLM output."""
        if not raw:
            return []
        try:
            result = json.loads(raw)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError as e:
            print(f"[LLMCleaner] JSON parse array error ({context}): {e}")
        return []

    @staticmethod
    def _parse_json_dict(raw: str, context: str = "") -> dict:
        """Parse a strict top-level JSON dict from LLM output."""
        if not raw:
            return {}
        try:
            result = json.loads(raw)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError as e:
            print(f"[LLMCleaner] JSON parse dict error ({context}): {e}")
        return {}

    def _get_column_rag_context(self, col_name: str, schema_hint: dict) -> str:
        """Retrieve concise cleaning guidance for this column from DataSoul brain."""
        if not self._rag or not self._rag.is_ready:
            return "No RAG rules available."
        semantic_type = schema_hint.get("semantic_type", "unknown")
        query = (
            f"data cleaning rules for column {col_name} semantic type {semantic_type}; "
            "normalization null strings type detection encoding outliers patterns"
        )
        try:
            context = self._rag.get_context_for_prompt(query, n_results=3)
            if context and "No relevant" not in context:
                return context[:1500]
        except Exception as e:
            print(f"[LLMCleaner] RAG lookup failed for '{col_name}': {e}")
        return "No relevant RAG rules retrieved."


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _audit(col: str, action: str, issue: str, desc: str,
           rows_affected: int, confidence: float) -> dict:
    return {
        "action": action,
        "column": col,
        "detail": desc or issue,
        "rows_affected": rows_affected,
        "confidence": int(confidence * 100),
        "source": "LLM-guided",
        "issue_type": issue,
    }
