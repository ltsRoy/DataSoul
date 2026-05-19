"""Deterministic data cleaning utilities — no LLM required.

Each function takes a pandas Series and returns a cleaned copy plus
an audit dict describing what changed. These are composable building
blocks used by CSVCorrector and the IterativePipeline.
"""

import re
import pandas as pd
import numpy as np
from typing import Optional


# ─── Null-like string constants ───

NULL_STRINGS = {
    "n/a", "na", "null", "none", "nil", "nan", "undefined",
    "-", "--", "---", ".", "..", "...",
    "#n/a", "#na", "#null", "#ref!", "#value!",
    "not available", "not applicable", "missing",
    "n.a.", "n.a", "n/d", "nd",
    "unknown",  # controversial — only used when column is clearly data, not a category
    "", " ",
}

# Common boolean mappings
BOOL_TRUE = {"yes", "y", "true", "t", "1", "on", "active", "enabled", "si", "oui", "हां"}
BOOL_FALSE = {"no", "n", "false", "f", "0", "off", "inactive", "disabled", "non", "नहीं"}


class DataCleaners:
    """Deterministic data cleaning utilities — no LLM required.

    Every method is a @staticmethod that takes a pandas Series and returns
    a tuple of (cleaned_series, audit_dict). The audit_dict contains:
      - action: str — the cleaning action name
      - column: str — populated by the caller
      - detail: str — human-readable description of what changed
      - rows_affected: int — number of values modified
      - confidence: int — 0-100
      - source: "deterministic"
    If nothing changed, returns (original_series, None).
    """

    # ─── Null String Cleaning ───

    @staticmethod
    def clean_null_strings(series: pd.Series, col_name: str = "",
                           extra_nulls: set[str] | None = None) -> tuple[pd.Series, dict | None]:
        """Convert common null-like strings ('N/A', 'null', '-', etc.) to actual NaN.

        Only applies to object (string) columns. Preserves actual NaN already present.
        """
        if not pd.api.types.is_object_dtype(series):
            return series, None

        null_set = NULL_STRINGS | (extra_nulls or set())
        mask = series.notna()
        if not mask.any():
            return series, None

        str_vals = series[mask].astype(str).str.strip()
        is_null_string = str_vals.str.lower().isin(null_set)
        count = int(is_null_string.sum())

        if count == 0:
            return series, None

        out = series.copy()
        # Set matched positions to NaN
        null_indices = str_vals[is_null_string].index
        out.loc[null_indices] = np.nan

        return out, {
            "action": "CLEAN_NULL_STRINGS",
            "column": col_name,
            "detail": f"Converted {count} null-like strings ('N/A', 'null', '-', etc.) to NaN",
            "rows_affected": count,
            "confidence": 96,
            "source": "deterministic",
        }

    # ─── Percentage Cleaning ───

    @staticmethod
    def clean_percentages(series: pd.Series, col_name: str = "",
                          divide_by_100: bool = False) -> tuple[pd.Series, dict | None]:
        """Strip '%' from values and convert to numeric.

        If divide_by_100=True, '45%' → 0.45. Otherwise '45%' → 45.0.
        Only triggers if >40% of non-null values match percentage pattern.
        """
        if not pd.api.types.is_object_dtype(series):
            return series, None

        clean = series.dropna().astype(str).str.strip()
        if len(clean) == 0:
            return series, None

        pct_pattern = r'^[+-]?\s*\d+[\d,]*\.?\d*\s*%$'
        matches = clean.str.match(pct_pattern, na=False)
        match_ratio = matches.sum() / len(clean)

        if pd.isna(match_ratio) or match_ratio < 0.4:
            return series, None

        out = series.astype("string").str.strip().str.replace('%', '', regex=False)
        out = out.str.replace(',', '', regex=False).str.strip()
        out = pd.to_numeric(out, errors='coerce')

        if divide_by_100:
            out = out / 100.0

        count = int(matches.sum())
        return out, {
            "action": "CLEAN_PERCENTAGES",
            "column": col_name,
            "detail": f"Stripped '%' from {count} values and converted to numeric"
                      + (" (divided by 100)" if divide_by_100 else ""),
            "rows_affected": count,
            "confidence": 94,
            "source": "deterministic",
        }

    # ─── Boolean Normalization ───

    @staticmethod
    def clean_booleans(series: pd.Series, col_name: str = "") -> tuple[pd.Series, dict | None]:
        """Normalize boolean-like strings ('Yes'/'No', 'T'/'F', etc.) to actual booleans.

        Only triggers if >70% of non-null values are boolean-like.
        """
        if not pd.api.types.is_object_dtype(series):
            return series, None

        clean = series.dropna().astype(str).str.strip().str.lower()
        if len(clean) == 0:
            return series, None

        all_bools = BOOL_TRUE | BOOL_FALSE
        is_bool = clean.isin(all_bools)
        bool_ratio = is_bool.sum() / len(clean)

        if pd.isna(bool_ratio) or bool_ratio < 0.7:
            return series, None

        out = series.copy()
        str_lower = series.astype(str).str.strip().str.lower()
        out = str_lower.map(
            lambda v: True if v in BOOL_TRUE else (False if v in BOOL_FALSE else np.nan)
        )
        # Preserve original NaN
        out[series.isna()] = np.nan

        count = int(is_bool.sum())
        return out, {
            "action": "NORMALIZE_BOOLEANS",
            "column": col_name,
            "detail": f"Normalized {count} boolean strings (Yes/No, T/F, etc.) to True/False",
            "rows_affected": count,
            "confidence": 93,
            "source": "deterministic",
        }

    # ─── Year Fixing ───

    @staticmethod
    def clean_years(series: pd.Series, col_name: str = "",
                    two_digit_cutoff: int = 30) -> tuple[pd.Series, dict | None]:
        """Fix year values: 2020.0 → 2020, two-digit years (85 → 1985).

        two_digit_cutoff: values <= cutoff become 20xx, > cutoff become 19xx.
        E.g., cutoff=30: 25 → 2025, 85 → 1985.
        Only applies to columns with 'year' in the name or values that look like years.
        """
        col_lower = col_name.lower()
        looks_like_year = any(h in col_lower for h in ["year", "yr", "fiscal", "fy"])

        clean = series.dropna()
        if len(clean) == 0:
            return series, None

        # Convert to string for pattern matching
        str_vals = clean.astype(str).str.strip()

        # Pattern 1: Float years (2020.0 → 2020)
        float_year = str_vals.str.match(r'^\d{4}\.0$', na=False)

        # Pattern 2: Valid 4-digit years
        four_digit = str_vals.str.match(r'^\d{4}$', na=False)

        # Pattern 3: Two-digit years (only if column name suggests year)
        two_digit = str_vals.str.match(r'^\d{1,2}$', na=False) if looks_like_year else pd.Series(False, index=str_vals.index)

        year_like = float_year | four_digit | two_digit
        year_ratio = year_like.sum() / len(clean)

        # Only proceed if enough values look like years and column name hints at it
        if year_ratio < 0.7 and not looks_like_year:
            return series, None
        if pd.isna(year_ratio) or year_ratio < 0.5:
            return series, None

        out = series.copy()
        non_null = out.notna()

        # Step 1: Strip .0 suffix
        out_str = out.astype("string").str.strip()
        out_str = out_str.str.replace(r'\.0$', '', regex=True)

        # Step 2: Convert to numeric
        numeric = pd.to_numeric(out_str, errors='coerce')

        # Step 3: Fix two-digit years
        if looks_like_year:
            is_two_digit = numeric.notna() & (numeric >= 0) & (numeric <= 99)
            numeric = numeric.where(
                ~is_two_digit,
                numeric.where(numeric > two_digit_cutoff, numeric + 2000).where(
                    numeric <= two_digit_cutoff, numeric + 1900
                )
            )
            # Fix: recalculate properly
            two_digit_mask = is_two_digit & numeric.notna()
            for idx in numeric[two_digit_mask].index:
                val = int(out_str.loc[idx]) if out_str.loc[idx] and out_str.loc[idx].isdigit() else 0
                if val <= two_digit_cutoff:
                    numeric.loc[idx] = 2000 + val
                else:
                    numeric.loc[idx] = 1900 + val

        # Validate: only keep values in reasonable year range
        valid_year = numeric.between(1900, 2100) | numeric.isna()
        numeric = numeric.where(valid_year, np.nan)

        out = numeric.astype("Int64")
        count = int((out.notna() & non_null).sum())

        if count == 0:
            return series, None

        return out, {
            "action": "CLEAN_YEARS",
            "column": col_name,
            "detail": f"Normalized {count} year values to integers (fixed floats, 2-digit years)",
            "rows_affected": count,
            "confidence": 95,
            "source": "deterministic",
        }

    # ─── Phone Number Normalization ───

    @staticmethod
    def clean_phone_numbers(series: pd.Series, col_name: str = "") -> tuple[pd.Series, dict | None]:
        """Normalize phone number formats — strip dashes, parens, spaces.

        Only triggers if column name contains phone/mobile/tel/contact hints.
        Preserves country code prefixes (+91, +1, etc.).
        """
        col_lower = col_name.lower()
        if not any(h in col_lower for h in ["phone", "mobile", "tel", "cell", "contact", "fax"]):
            return series, None

        if not pd.api.types.is_object_dtype(series):
            return series, None

        clean = series.dropna().astype(str).str.strip()
        if len(clean) == 0:
            return series, None

        # Check if values look like phone numbers
        phone_pattern = r'^[\+]?[\d\s\-\.\(\)]{7,18}$'
        looks_phone = clean.str.match(phone_pattern, na=False)
        phone_ratio = looks_phone.sum() / len(clean)

        if pd.isna(phone_ratio) or phone_ratio < 0.5:
            return series, None

        out = series.copy()
        non_null = out.notna()

        def normalize_phone(val):
            if pd.isna(val):
                return val
            s = str(val).strip()
            # Preserve leading +
            has_plus = s.startswith('+')
            # Strip formatting characters
            digits = re.sub(r'[\s\-\.\(\)]', '', s)
            if has_plus and not digits.startswith('+'):
                digits = '+' + digits
            return digits

        out[non_null] = out[non_null].apply(normalize_phone)
        changed = int((out[non_null].astype(str) != series[non_null].astype(str)).sum())

        if changed == 0:
            return series, None

        return out, {
            "action": "NORMALIZE_PHONES",
            "column": col_name,
            "detail": f"Normalized {changed} phone numbers (stripped dashes, parens, spaces)",
            "rows_affected": changed,
            "confidence": 90,
            "source": "deterministic",
        }

    # ─── Whitespace / Invisible Character Cleaning ───

    @staticmethod
    def clean_whitespace(series: pd.Series, col_name: str = "") -> tuple[pd.Series, dict | None]:
        """Strip zero-width characters, non-breaking spaces, excessive internal whitespace,
        embedded newlines/tabs from string values.
        """
        if not pd.api.types.is_object_dtype(series):
            return series, None

        non_null = series.notna()
        if not non_null.any():
            return series, None

        original = series[non_null].astype(str)

        cleaned = original.copy()
        # Replace zero-width and non-breaking spaces
        cleaned = cleaned.str.replace('\u200b', '', regex=False)  # zero-width space
        cleaned = cleaned.str.replace('\u200c', '', regex=False)  # zero-width non-joiner
        cleaned = cleaned.str.replace('\u200d', '', regex=False)  # zero-width joiner
        cleaned = cleaned.str.replace('\ufeff', '', regex=False)  # BOM
        cleaned = cleaned.str.replace('\xa0', ' ', regex=False)   # non-breaking space
        # Replace tabs and newlines with space
        cleaned = cleaned.str.replace(r'[\t\r\n]+', ' ', regex=True)
        # Collapse multiple spaces
        cleaned = cleaned.str.replace(r'\s{2,}', ' ', regex=True)
        # Strip leading/trailing
        cleaned = cleaned.str.strip()

        changed = (cleaned != original)
        count = int(changed.sum())

        if count == 0:
            return series, None

        out = series.copy()
        out[non_null] = cleaned

        return out, {
            "action": "CLEAN_WHITESPACE",
            "column": col_name,
            "detail": f"Fixed whitespace/invisible chars in {count} values "
                      "(zero-width, NBSP, tabs, excessive spaces)",
            "rows_affected": count,
            "confidence": 98,
            "source": "deterministic",
        }

    # ─── Indian Number Notation ───

    @staticmethod
    def clean_indian_numbers(series: pd.Series, col_name: str = "") -> tuple[pd.Series, dict | None]:
        """Handle Indian number notation: '1,23,456' → 123456.

        Indian system uses groups of 2 after the first 3 digits:
        1,23,45,678 or 12,34,567. This differs from Western 123,456,789.
        Only triggers if values match Indian grouping patterns.
        """
        if not pd.api.types.is_object_dtype(series):
            return series, None

        clean = series.dropna().astype(str).str.strip()
        if len(clean) == 0:
            return series, None

        # Indian notation: last group is 3 digits, earlier groups are 2 digits
        # e.g., 1,23,456 or 12,34,567 or 1,00,000
        indian_pattern = r'^\d{1,2}(,\d{2})*(,\d{3})(\.\d+)?$'
        matches = clean.str.match(indian_pattern, na=False)
        match_count = int(matches.sum())

        # Also check for Western notation to avoid false positives
        western_pattern = r'^\d{1,3}(,\d{3})+(\.\d+)?$'
        western_matches = clean.str.match(western_pattern, na=False)

        # Only apply Indian cleaning if Indian pattern matches significantly
        # and more than Western pattern (or Western doesn't match at all)
        if match_count < 3 or match_count / len(clean) < 0.3:
            return series, None

        # If western matches everything Indian matches, it's ambiguous — skip
        if western_matches.sum() >= match_count:
            return series, None

        out = series.copy()
        non_null = out.notna()
        stripped = out.astype("string").str.replace(',', '', regex=False).str.strip()
        numeric = pd.to_numeric(stripped, errors='coerce')

        converted = int(numeric.notna().sum())
        if converted == 0:
            return series, None

        return numeric, {
            "action": "CLEAN_INDIAN_NUMBERS",
            "column": col_name,
            "detail": f"Converted {match_count} Indian-notation numbers (e.g. 1,23,456) to numeric",
            "rows_affected": match_count,
            "confidence": 88,
            "source": "deterministic",
        }

    # ─── Date Normalization ───

    @staticmethod
    def normalize_dates(series: pd.Series, col_name: str = "",
                        target_format: str = "%Y-%m-%d") -> tuple[pd.Series, dict | None]:
        """Normalize mixed date formats to a consistent format (default: ISO 8601).

        Handles: DD/MM/YYYY, MM-DD-YYYY, "Jan 15, 2023", "15 March 2021",
        "March 2021" (partial), and various separator styles.
        Only triggers if column name hints at dates or >50% of values parse as dates.
        """
        col_lower = col_name.lower()
        looks_like_date = any(h in col_lower for h in [
            "date", "time", "created", "updated", "timestamp",
            "reported", "started", "ended", "dob", "birth", "expir",
        ])

        if not pd.api.types.is_object_dtype(series):
            return series, None

        clean = series.dropna().astype(str).str.strip()
        if len(clean) == 0:
            return series, None

        # Skip if values look like pure years (handled by clean_years)
        year_only = clean.str.match(r'^\d{4}(\.0)?$', na=False)
        if year_only.sum() / len(clean) > 0.7:
            return series, None

        # Try parsing with pandas
        try:
            parsed = pd.to_datetime(clean, format='mixed', dayfirst=False, errors='coerce')
            parse_ratio = parsed.notna().sum() / len(clean)

            # Need at least 50% parse rate, or column name hint + 30%
            threshold = 0.3 if looks_like_date else 0.5
            if parse_ratio < threshold:
                return series, None

            # Check if there are multiple formats (the actual problem we're solving)
            # If everything is already in one format, don't re-format
            original_formats = set()
            for val in clean.head(50):
                if re.match(r'\d{4}-\d{2}-\d{2}', val):
                    original_formats.add('ISO')
                elif re.match(r'\d{1,2}/\d{1,2}/\d{4}', val):
                    original_formats.add('SLASH')
                elif re.match(r'\d{1,2}-\d{1,2}-\d{4}', val):
                    original_formats.add('DASH')
                elif re.match(r'\d{1,2}\.\d{1,2}\.\d{4}', val):
                    original_formats.add('DOT')
                elif re.search(r'[A-Za-z]', val):
                    original_formats.add('NAMED')

            # Apply datetime conversion
            out = pd.to_datetime(series, format='mixed', dayfirst=False, errors='coerce')
            converted = int(out.notna().sum())

            if converted == 0:
                return series, None

            detail = f"Parsed {converted} date values to datetime"
            if len(original_formats) > 1:
                detail += f" (unified {len(original_formats)} formats: {', '.join(sorted(original_formats))})"

            return out, {
                "action": "NORMALIZE_DATES",
                "column": col_name,
                "detail": detail,
                "rows_affected": converted,
                "confidence": 90 if looks_like_date else 82,
                "source": "deterministic",
            }

        except Exception:
            return series, None

    # ─── Negative Parentheses ───

    @staticmethod
    def clean_negative_parens(series: pd.Series, col_name: str = "") -> tuple[pd.Series, dict | None]:
        """Convert accounting-style negatives: '(500)' → -500, '(1,234.56)' → -1234.56.

        Common in financial data exported from Excel/accounting software.
        Only triggers if >10% of values use parenthetical notation.
        """
        if not pd.api.types.is_object_dtype(series):
            return series, None

        clean = series.dropna().astype(str).str.strip()
        if len(clean) == 0:
            return series, None

        # Pattern: (123), (1,234), (1,234.56), ($1,234)
        paren_pattern = r'^\([\$₹£€¥]?\s*[\d,]+\.?\d*\)$'
        matches = clean.str.match(paren_pattern, na=False)
        match_count = int(matches.sum())

        if match_count < 2 or match_count / len(clean) < 0.05:
            return series, None

        out = series.copy()
        non_null = out.notna()
        str_vals = out[non_null].astype(str).str.strip()

        def convert_paren(val):
            s = str(val).strip()
            if re.match(paren_pattern, s):
                # Remove parens, currency symbols, commas
                inner = s[1:-1].strip()
                inner = re.sub(r'[\$₹£€¥,\s]', '', inner)
                try:
                    return -float(inner)
                except ValueError:
                    return val
            return val

        out[non_null] = str_vals.apply(convert_paren)

        # Try to convert entire column to numeric now
        numeric = pd.to_numeric(out, errors='coerce')
        numeric_ratio = numeric.notna().sum() / max(non_null.sum(), 1)

        if numeric_ratio > 0.6:
            out = numeric

        return out, {
            "action": "CLEAN_NEGATIVE_PARENS",
            "column": col_name,
            "detail": f"Converted {match_count} parenthetical negatives '(500)' → -500",
            "rows_affected": match_count,
            "confidence": 94,
            "source": "deterministic",
        }

    # ─── Email Normalization ───

    @staticmethod
    def clean_emails(series: pd.Series, col_name: str = "") -> tuple[pd.Series, dict | None]:
        """Normalize email addresses: lowercase, trim, fix common domain typos.

        Only triggers if column name contains email/mail hint.
        """
        col_lower = col_name.lower()
        if not any(h in col_lower for h in ["email", "mail", "e-mail", "e_mail"]):
            return series, None

        if not pd.api.types.is_object_dtype(series):
            return series, None

        non_null = series.notna()
        if not non_null.any():
            return series, None

        original = series[non_null].astype(str)
        cleaned = original.str.strip().str.lower()

        # Fix common domain typos
        domain_fixes = {
            "gmial.com": "gmail.com",
            "gmaill.com": "gmail.com",
            "gamil.com": "gmail.com",
            "gmai.com": "gmail.com",
            "gmail.co": "gmail.com",
            "yaho.com": "yahoo.com",
            "yahooo.com": "yahoo.com",
            "hotmal.com": "hotmail.com",
            "hotmial.com": "hotmail.com",
            "outlok.com": "outlook.com",
        }

        for typo, fix in domain_fixes.items():
            cleaned = cleaned.str.replace(rf'@{typo}$', f'@{fix}', regex=True)

        changed = (cleaned != original.str.strip())
        count = int(changed.sum())

        if count == 0:
            return series, None

        out = series.copy()
        out[non_null] = cleaned

        return out, {
            "action": "NORMALIZE_EMAILS",
            "column": col_name,
            "detail": f"Normalized {count} email addresses (lowercased, fixed typos)",
            "rows_affected": count,
            "confidence": 92,
            "source": "deterministic",
        }

    # ─── Text Prefix Stripping ───

    # Common label prefixes that contaminate real values
    _KNOWN_PREFIXES: list[str] = [
        "written by:", "writtenby:", "written by",
        "narrated by:", "narratedby:", "narrated by",
        "translated by:", "translatedby:",
        "edited by:", "editedby:",
        "author:", "authors:",
        "narrator:", "narrators:",
        "publisher:", "published by:",
        "director:", "directed by:",
    ]

    @classmethod
    def clean_text_prefixes(
        cls,
        series: pd.Series,
        col_name: str = "",
        extra_prefixes: list[str] | None = None,
    ) -> tuple[pd.Series, dict | None]:
        """Strip well-known label prefixes (e.g. 'Writtenby:', 'Narratedby:') from string values.

        Triggers when ≥30 % of non-null values carry a known prefix so that
        it doesn't accidentally fire on columns that contain sentences.
        """
        if not pd.api.types.is_object_dtype(series):
            return series, None

        non_null_mask = series.notna()
        if not non_null_mask.any():
            return series, None

        all_prefixes = cls._KNOWN_PREFIXES + (extra_prefixes or [])
        str_vals = series[non_null_mask].astype(str)

        def _has_prefix(v: str) -> bool:
            low = v.strip().lower()
            return any(low.startswith(p) for p in all_prefixes)

        prefix_hits = str_vals.apply(_has_prefix)
        hit_ratio = prefix_hits.sum() / len(str_vals)

        if hit_ratio < 0.3:
            return series, None

        def _strip_prefix(v: str) -> str:
            low = v.strip().lower()
            for p in all_prefixes:
                if low.startswith(p):
                    return v.strip()[len(p):].strip()
            return v.strip()

        out = series.copy()
        out[non_null_mask] = str_vals.apply(_strip_prefix)

        count = int(prefix_hits.sum())
        return out, {
            "action": "STRIP_TEXT_PREFIXES",
            "column": col_name,
            "detail": f"Stripped label prefixes (e.g. 'Writtenby:', 'Narratedby:') from {count} values",
            "rows_affected": count,
            "confidence": 95,
            "source": "deterministic",
        }

    # ─── Rating String Extraction ───

    @staticmethod
    def clean_rating_strings(
        series: pd.Series,
        col_name: str = "",
    ) -> tuple[pd.Series, dict | None]:
        """Extract the lead numeric rating from strings like '4.5 out of 5 stars 234 ratings'.

        Converts the series to a float column containing only the rating value.
        Only triggers when ≥40 % of non-null values match the pattern.
        """
        if not pd.api.types.is_object_dtype(series):
            return series, None

        non_null_mask = series.notna()
        if not non_null_mask.any():
            return series, None

        str_vals = series[non_null_mask].astype(str).str.strip()

        # Pattern: optional leading digit(s)+decimal, then ' out of N stars ...
        #           OR plain numeric string after stripping
        rating_re = re.compile(
            r'^([0-9]+(?:\.[0-9]+)?)\s+out\s+of\s+[0-9]+\s+stars?',
            re.IGNORECASE,
        )
        matches = str_vals.apply(lambda v: bool(rating_re.match(v)))
        match_ratio = matches.sum() / len(str_vals)

        if match_ratio < 0.4:
            return series, None

        def _extract(v: str) -> float | None:
            m = rating_re.match(v)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    return None
            return None

        extracted = str_vals.apply(_extract)
        out = series.copy().astype(object)
        out[non_null_mask] = extracted
        out = pd.to_numeric(out, errors='coerce')

        count = int(matches.sum())
        return out, {
            "action": "EXTRACT_RATING",
            "column": col_name,
            "detail": f"Extracted numeric rating from {count} '… out of N stars …' strings",
            "rows_affected": count,
            "confidence": 97,
            "source": "deterministic",
        }

    # ─── Orchestrator ───

    @classmethod
    def run_all(cls, df: pd.DataFrame, column_hints: dict | None = None) -> tuple[pd.DataFrame, list[dict]]:
        """Run all deterministic cleaners on a DataFrame.

        Returns (cleaned_df, list_of_audit_entries).
        column_hints: optional dict mapping column names to semantic types
                      (e.g., {"DOB": "date", "Salary": "currency"}).
        """
        df_out = df.copy()
        audit = []

        # Order matters: null strings first (so downstream cleaners see NaN not "N/A"),
        # then whitespace, then type-specific cleaners.
        cleaner_sequence = [
            ("null_strings", cls.clean_null_strings),
            ("whitespace", cls.clean_whitespace),
            # --- content-aware cleaners (run before type coercion) ---
            ("text_prefixes", cls.clean_text_prefixes),   # strip 'Writtenby:' etc.
            ("rating_strings", cls.clean_rating_strings),  # '4.5 out of 5 stars…' → 4.5
            # --- type coercion cleaners ---
            ("percentages", cls.clean_percentages),
            ("booleans", cls.clean_booleans),
            ("negative_parens", cls.clean_negative_parens),
            ("emails", cls.clean_emails),
            ("phone_numbers", cls.clean_phone_numbers),
            ("indian_numbers", cls.clean_indian_numbers),
            ("years", cls.clean_years),
            ("dates", cls.normalize_dates),
        ]

        for col in list(df_out.columns):
            for cleaner_name, cleaner_fn in cleaner_sequence:
                # Skip if column was already converted to non-object by a previous cleaner
                if cleaner_name in ("percentages", "booleans", "negative_parens",
                                    "emails", "phone_numbers", "indian_numbers",
                                    "null_strings", "whitespace",
                                    "text_prefixes") \
                        and not pd.api.types.is_object_dtype(df_out[col]):
                    continue

                # rating_strings converts the column to numeric — skip if already numeric
                if cleaner_name == "rating_strings" \
                        and not pd.api.types.is_object_dtype(df_out[col]):
                    continue

                try:
                    cleaned, audit_entry = cleaner_fn(df_out[col], col_name=col)
                    if audit_entry is not None:
                        df_out[col] = cleaned
                        audit.append(audit_entry)
                except Exception as e:
                    print(f"[DataCleaners] {cleaner_name} failed for '{col}': {e}")

        return df_out, audit
