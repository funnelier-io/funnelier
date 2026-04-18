"""
Tests for ETL / Data Import — Sprint 1 P0 Gap Closure.

Covers:
- ETL helper functions (_normalize_phone, _parse_duration, _find_phone_column, etc.)
- ImportResult / ImportSummary / AsyncTaskResponse schemas
- Category & salesperson extraction from filenames
"""

import pytest
import pandas as pd

from src.modules.etl.api.routes import (
    ImportResult,
    ImportSummary,
    AsyncTaskResponse,
    _normalize_phone,
    _parse_duration,
    _find_phone_column,
    _find_name_column,
    _find_column,
    _extract_category,
    _extract_salesperson,
)


# ═══════════════════════════════════════════════════════════════════
# Phone Number Normalization
# ═══════════════════════════════════════════════════════════════════


class TestNormalizePhone:
    """Tests for _normalize_phone helper."""

    def test_international_format_with_98(self):
        assert _normalize_phone("989123456789") == "9123456789"

    def test_local_format_with_zero(self):
        assert _normalize_phone("09123456789") == "9123456789"

    def test_raw_ten_digits(self):
        assert _normalize_phone("9123456789") == "9123456789"

    def test_float_format_from_excel(self):
        """Excel often stores phone numbers as floats."""
        assert _normalize_phone("9.123456789E9") == "9123456789"

    def test_empty_string_returns_none(self):
        assert _normalize_phone("") is None

    def test_none_returns_none(self):
        assert _normalize_phone(None) is None

    def test_too_short_returns_none(self):
        assert _normalize_phone("912345") is None

    def test_non_digit_chars_stripped(self):
        assert _normalize_phone("+98-912-345-6789") == "9123456789"

    def test_landline_number_returns_none(self):
        """Landlines don't start with 9; should be rejected."""
        assert _normalize_phone("02112345678") is None

    def test_integer_input(self):
        assert _normalize_phone("9123456789") == "9123456789"

    def test_international_twelve_digits(self):
        assert _normalize_phone("989351234567") == "9351234567"

    def test_starts_not_with_nine_returns_none(self):
        assert _normalize_phone("1234567890") is None


# ═══════════════════════════════════════════════════════════════════
# Duration Parsing
# ═══════════════════════════════════════════════════════════════════


class TestParseDuration:
    """Tests for _parse_duration helper."""

    def test_seconds_string(self):
        assert _parse_duration("366 sec") == 366

    def test_minutes_only(self):
        assert _parse_duration("2 min") == 120

    def test_minutes_and_seconds(self):
        assert _parse_duration("2 min 30 sec") == 150

    def test_plain_integer(self):
        assert _parse_duration("90") == 90

    def test_float_string(self):
        assert _parse_duration("120.5") == 120

    def test_none_returns_zero(self):
        assert _parse_duration(None) == 0

    def test_nan_returns_zero(self):
        assert _parse_duration(float("nan")) == 0

    def test_empty_string_returns_zero(self):
        assert _parse_duration("") == 0

    def test_invalid_text_returns_zero(self):
        assert _parse_duration("hello") == 0

    def test_comma_separated_number(self):
        assert _parse_duration("1,200") == 1200


# ═══════════════════════════════════════════════════════════════════
# Column Detection
# ═══════════════════════════════════════════════════════════════════


class TestFindPhoneColumn:
    """Tests for _find_phone_column helper."""

    def test_exact_english_name(self):
        df = pd.DataFrame({"phone": ["09121234567"], "name": ["Ali"]})
        assert _find_phone_column(df) == "phone"

    def test_persian_name(self):
        df = pd.DataFrame({"شماره موبایل": ["09121234567"], "نام": ["علی"]})
        assert _find_phone_column(df) == "شماره موبایل"

    def test_partial_match(self):
        df = pd.DataFrame({"phone_number": ["09121234567"]})
        assert _find_phone_column(df) == "phone_number"

    def test_mobile_column(self):
        df = pd.DataFrame({"Mobile": ["09121234567"]})
        assert _find_phone_column(df) == "Mobile"

    def test_heuristic_detection(self):
        """Falls back to heuristic when no column name matches."""
        df = pd.DataFrame({
            "col_a": [f"912{i:07d}" for i in range(10)],
            "col_b": [f"name_{i}" for i in range(10)],
        })
        result = _find_phone_column(df)
        assert result == "col_a"

    def test_no_phone_column_returns_none(self):
        df = pd.DataFrame({"city": ["Tehran"], "age": [30]})
        assert _find_phone_column(df) is None


class TestFindNameColumn:
    """Tests for _find_name_column helper."""

    def test_english_name(self):
        df = pd.DataFrame({"name": ["Ali"], "phone": ["0912"]})
        assert _find_name_column(df) == "name"

    def test_persian_name(self):
        df = pd.DataFrame({"نام": ["علی"]})
        assert _find_name_column(df) == "نام"

    def test_full_name_variant(self):
        df = pd.DataFrame({"نام و نام خانوادگی": ["علی رضایی"]})
        assert _find_name_column(df) == "نام و نام خانوادگی"

    def test_no_name_column_returns_none(self):
        df = pd.DataFrame({"phone": ["0912"], "city": ["Tehran"]})
        assert _find_name_column(df) is None


class TestFindColumn:
    """Tests for _find_column generic helper."""

    def test_finds_matching_column(self):
        df = pd.DataFrame({"duration": [100], "phone": ["0912"]})
        assert _find_column(df, ["duration", "مدت"]) == "duration"

    def test_finds_persian_variant(self):
        df = pd.DataFrame({"مدت": [100]})
        assert _find_column(df, ["duration", "مدت"]) == "مدت"

    def test_case_insensitive(self):
        df = pd.DataFrame({"Duration": [100]})
        assert _find_column(df, ["duration"]) == "Duration"

    def test_returns_none_when_no_match(self):
        df = pd.DataFrame({"col_a": [1]})
        assert _find_column(df, ["nonexistent"]) is None


# ═══════════════════════════════════════════════════════════════════
# Filename Extraction
# ═══════════════════════════════════════════════════════════════════


class TestExtractCategory:
    """Tests for _extract_category helper."""

    def test_persian_filename(self):
        result = _extract_category("خریداران سیمان.xlsx")
        assert result == "خریداران سیمان"

    def test_removes_report_prefix(self):
        result = _extract_category("report_All_تهران رضایی.xlsx")
        assert "report_All_" not in result

    def test_handles_special_chars(self):
        result = _extract_category("«سازندگان گیلان 2».xlsx")
        assert result == "«سازندگان گیلان 2»"

    def test_simple_name(self):
        result = _extract_category("leads.xlsx")
        assert result == "leads"


class TestExtractSalesperson:
    """Tests for _extract_salesperson helper."""

    def test_standard_format(self):
        result = _extract_salesperson("report_All_01_Mar-16_Feb - asadollahi.csv")
        assert result == "asadollahi"

    def test_bordbar(self):
        result = _extract_salesperson("report_All_03_Dec-16_Feb - bordbar.csv")
        assert result == "bordbar"

    def test_no_dash_returns_stem(self):
        result = _extract_salesperson("some_file.csv")
        assert result == "some_file"

    def test_multiple_dashes(self):
        result = _extract_salesperson("a - b - final_name.csv")
        assert result == "final_name"


# ═══════════════════════════════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════════════════════════════


class TestImportResultSchema:
    """Tests for ImportResult schema."""

    def test_minimal_creation(self):
        r = ImportResult(file_name="test.xlsx")
        assert r.file_name == "test.xlsx"
        assert r.total_records == 0
        assert r.imported == 0
        assert r.duplicates == 0
        assert r.errors == 0
        assert r.error_details == []

    def test_full_creation(self):
        r = ImportResult(
            file_name="leads.xlsx",
            category="سازندگان",
            total_records=100,
            imported=80,
            duplicates=15,
            errors=5,
            error_details=["Row 3: bad phone"],
        )
        assert r.total_records == 100
        assert r.imported == 80
        assert r.category == "سازندگان"
        assert len(r.error_details) == 1


class TestImportSummarySchema:
    def test_creation(self):
        result = ImportResult(file_name="a.xlsx", imported=10)
        s = ImportSummary(
            files_processed=1,
            total_imported=10,
            total_duplicates=0,
            total_errors=0,
            results=[result],
        )
        assert s.files_processed == 1
        assert len(s.results) == 1

    def test_multiple_results(self):
        results = [
            ImportResult(file_name=f"file_{i}.xlsx", imported=i * 10)
            for i in range(5)
        ]
        s = ImportSummary(
            files_processed=5,
            total_imported=sum(r.imported for r in results),
            total_duplicates=0,
            total_errors=0,
            results=results,
        )
        assert s.files_processed == 5
        assert s.total_imported == 100


class TestAsyncTaskResponseSchema:
    def test_defaults(self):
        r = AsyncTaskResponse(task_id="abc-123")
        assert r.task_id == "abc-123"
        assert r.status == "queued"
        assert r.message == ""

    def test_custom_message(self):
        r = AsyncTaskResponse(
            task_id="task-1",
            status="processing",
            message="Import in progress",
        )
        assert r.status == "processing"
        assert "Import" in r.message

