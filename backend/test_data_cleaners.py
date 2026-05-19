"""Unit tests for DataCleaners — deterministic data cleaning utilities."""

import pandas as pd
import numpy as np
import pytest

from data_cleaners import DataCleaners


class TestCleanNullStrings:
    def test_converts_common_nulls(self):
        s = pd.Series(["hello", "N/A", "null", "None", "world", "-", "."])
        cleaned, audit = DataCleaners.clean_null_strings(s, "test_col")
        assert audit is not None
        assert audit["action"] == "CLEAN_NULL_STRINGS"
        assert audit["rows_affected"] == 5  # N/A, null, None, -, .
        assert pd.isna(cleaned.iloc[1])
        assert pd.isna(cleaned.iloc[2])
        assert cleaned.iloc[0] == "hello"
        assert cleaned.iloc[4] == "world"

    def test_case_insensitive(self):
        s = pd.Series(["n/a", "NA", "Null", "NONE", "valid"])
        cleaned, audit = DataCleaners.clean_null_strings(s, "col")
        assert audit["rows_affected"] == 4

    def test_preserves_existing_nan(self):
        s = pd.Series(["hello", np.nan, "N/A"])
        cleaned, audit = DataCleaners.clean_null_strings(s, "col")
        assert pd.isna(cleaned.iloc[1])  # original NaN
        assert pd.isna(cleaned.iloc[2])  # converted N/A

    def test_no_change_returns_none(self):
        s = pd.Series(["hello", "world", "valid"])
        _, audit = DataCleaners.clean_null_strings(s, "col")
        assert audit is None

    def test_skips_numeric_columns(self):
        s = pd.Series([1, 2, 3])
        _, audit = DataCleaners.clean_null_strings(s, "col")
        assert audit is None


class TestCleanPercentages:
    def test_strips_percent(self):
        s = pd.Series(["45%", "78.5%", "100%", "N/A"])
        cleaned, audit = DataCleaners.clean_percentages(s, "col")
        assert audit is not None
        assert audit["action"] == "CLEAN_PERCENTAGES"
        assert abs(cleaned.iloc[0] - 45.0) < 0.01
        assert abs(cleaned.iloc[1] - 78.5) < 0.01

    def test_divide_by_100(self):
        s = pd.Series(["45%", "78%"])
        cleaned, audit = DataCleaners.clean_percentages(s, "col", divide_by_100=True)
        assert abs(cleaned.iloc[0] - 0.45) < 0.01

    def test_skips_if_low_ratio(self):
        s = pd.Series(["hello", "world", "45%", "test", "more"])
        _, audit = DataCleaners.clean_percentages(s, "col")
        assert audit is None  # only 1/5 = 20% < 40% threshold


class TestCleanBooleans:
    def test_normalizes_yes_no(self):
        s = pd.Series(["Yes", "No", "yes", "NO", "Y", "N"])
        cleaned, audit = DataCleaners.clean_booleans(s, "col")
        assert audit is not None
        assert cleaned.iloc[0] == True
        assert cleaned.iloc[1] == False
        assert cleaned.iloc[4] == True
        assert cleaned.iloc[5] == False

    def test_normalizes_true_false(self):
        s = pd.Series(["True", "False", "true", "FALSE", "T", "F"])
        cleaned, audit = DataCleaners.clean_booleans(s, "col")
        assert audit is not None
        assert cleaned.iloc[0] == True
        assert cleaned.iloc[1] == False

    def test_skips_if_not_boolean_like(self):
        s = pd.Series(["apple", "banana", "cherry", "yes"])
        _, audit = DataCleaners.clean_booleans(s, "col")
        assert audit is None  # only 1/4 = 25% < 70%


class TestCleanYears:
    def test_float_years(self):
        s = pd.Series(["2020.0", "2021.0", "2022.0"])
        cleaned, audit = DataCleaners.clean_years(s, "Year")
        assert audit is not None
        assert cleaned.iloc[0] == 2020
        assert cleaned.iloc[1] == 2021

    def test_two_digit_years(self):
        s = pd.Series(["85", "90", "05", "22"])
        cleaned, audit = DataCleaners.clean_years(s, "Year")
        assert audit is not None
        assert cleaned.iloc[0] == 1985
        assert cleaned.iloc[1] == 1990
        assert cleaned.iloc[2] == 2005
        assert cleaned.iloc[3] == 2022

    def test_skips_non_year_column(self):
        s = pd.Series(["hello", "world"])
        _, audit = DataCleaners.clean_years(s, "Name")
        assert audit is None


class TestCleanPhoneNumbers:
    def test_normalizes_formats(self):
        s = pd.Series(["(555) 123-4567", "+1-555-123-4567", "555.123.4567"])
        cleaned, audit = DataCleaners.clean_phone_numbers(s, "Phone")
        assert audit is not None
        # All should have no dashes/parens/dots
        for val in cleaned:
            assert '(' not in str(val)
            assert ')' not in str(val)
            assert '-' not in str(val)
            assert '.' not in str(val)

    def test_skips_non_phone_column(self):
        s = pd.Series(["hello", "world"])
        _, audit = DataCleaners.clean_phone_numbers(s, "Name")
        assert audit is None


class TestCleanWhitespace:
    def test_strips_invisible_chars(self):
        s = pd.Series(["hello\u200b world", "test\xa0value", "  extra  spaces  "])
        cleaned, audit = DataCleaners.clean_whitespace(s, "col")
        assert audit is not None
        assert "hello" in cleaned.iloc[0]
        assert "\u200b" not in cleaned.iloc[0]
        assert "\xa0" not in cleaned.iloc[1]

    def test_collapses_multiple_spaces(self):
        s = pd.Series(["too   many   spaces"])
        cleaned, audit = DataCleaners.clean_whitespace(s, "col")
        assert audit is not None
        assert "  " not in cleaned.iloc[0]


class TestNormalizeDates:
    def test_mixed_formats(self):
        s = pd.Series(["2023-01-15", "01/15/2023", "Jan 15, 2023"])
        cleaned, audit = DataCleaners.normalize_dates(s, "created_date")
        assert audit is not None
        assert audit["action"] == "NORMALIZE_DATES"
        assert pd.api.types.is_datetime64_any_dtype(cleaned)

    def test_skips_year_only(self):
        s = pd.Series(["2020", "2021", "2022"])
        _, audit = DataCleaners.normalize_dates(s, "Year")
        assert audit is None  # Years handled by clean_years


class TestCleanNegativeParens:
    def test_accounting_negatives(self):
        s = pd.Series(["100", "(200)", "300", "(400.50)"])
        cleaned, audit = DataCleaners.clean_negative_parens(s, "col")
        assert audit is not None
        assert audit["rows_affected"] == 2

    def test_with_currency(self):
        s = pd.Series(["$100", "($200)", "$300", "($400)"])
        cleaned, audit = DataCleaners.clean_negative_parens(s, "col")
        assert audit is not None


class TestCleanEmails:
    def test_normalizes_and_fixes_typos(self):
        s = pd.Series(["User@GMAIL.COM", "test@gmial.com", "hello@yahoo.com"])
        cleaned, audit = DataCleaners.clean_emails(s, "Email")
        assert audit is not None
        assert cleaned.iloc[0] == "user@gmail.com"
        assert cleaned.iloc[1] == "test@gmail.com"

    def test_skips_non_email_column(self):
        s = pd.Series(["test@gmail.com"])
        _, audit = DataCleaners.clean_emails(s, "Name")
        assert audit is None


class TestRunAll:
    def test_full_pipeline(self):
        df = pd.DataFrame({
            "Name": ["Alice", "Bob", "N/A", "Charlie"],
            "Score": ["85%", "90%", "75%", "100%"],
            "Active": ["Yes", "No", "Yes", "No"],
            "Year": ["2020.0", "2021.0", "2022.0", "2023.0"],
            "Email": ["Test@GMAIL.COM", "user@yahoo.com", "foo@gmial.com", "bar@outlook.com"],
        })
        cleaned, audit = DataCleaners.run_all(df)

        assert len(audit) > 0
        actions = {a["action"] for a in audit}
        # Should have cleaned null strings, percentages, booleans, years, emails
        assert "CLEAN_NULL_STRINGS" in actions
        assert "CLEAN_PERCENTAGES" in actions
        assert "NORMALIZE_BOOLEANS" in actions
        assert "CLEAN_YEARS" in actions
        assert "NORMALIZE_EMAILS" in actions

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        cleaned, audit = DataCleaners.run_all(df)
        assert len(audit) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
