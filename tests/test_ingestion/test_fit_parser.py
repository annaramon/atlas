from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.ingestion.fit_parser import parse_fit_file


def _make_path(name: str) -> Path:
    """Return a fake Path with the given filename (file doesn't need to exist — fitparse is mocked)."""
    p = MagicMock(spec=Path)
    p.name = name
    p.stem = name.removesuffix(".fit")
    p.__str__ = lambda self: f"/fake/{name}"
    return p


def _mock_session(overrides: dict = {}):
    """Build a mock FIT session message with sensible defaults."""
    start_time = datetime(2025, 3, 15, 9, 0, 0)  # naive UTC, as fitparse returns
    defaults = {
        "start_time": start_time,
        "total_timer_time": 3600,
        "total_distance": 10000.0,
        "total_ascent": 250.0,
        "total_calories": 650,
        "avg_heart_rate": 148,
        "max_heart_rate": 172,
        "min_heart_rate": 98,
        "time_in_hr_zone": [600.0, 1200.0, 900.0, 600.0, 300.0],
    }
    defaults.update(overrides)

    msg = MagicMock()
    msg.get_value = lambda field: defaults.get(field)
    return msg


def _patch_fitparse(sessions: list):
    fit_file = MagicMock()
    fit_file.get_messages.return_value = sessions
    return patch("app.ingestion.fit_parser.fitparse.FitFile", return_value=fit_file)


# ---------------------------------------------------------------------------
# Filename parsing
# ---------------------------------------------------------------------------

def test_bad_filename_returns_none():
    p = _make_path("bad_filename.fit")
    with _patch_fitparse([_mock_session()]):
        result = parse_fit_file(p)
    assert result is None


def test_sport_type_parsed_from_filename():
    p = _make_path("2025-03-15_09.00.00-cross_country_skiing.fit")
    with _patch_fitparse([_mock_session()]):
        result = parse_fit_file(p)
    assert result is not None
    assert result["sport_type"] == "cross_country_skiing"


def test_source_file_is_filename():
    p = _make_path("2025-03-15_09.00.00-running.fit")
    with _patch_fitparse([_mock_session()]):
        result = parse_fit_file(p)
    assert result["source_file"] == "2025-03-15_09.00.00-running.fit"


# ---------------------------------------------------------------------------
# Session message presence
# ---------------------------------------------------------------------------

def test_no_session_message_returns_none():
    p = _make_path("2025-03-15_09.00.00-running.fit")
    with _patch_fitparse([]):
        result = parse_fit_file(p)
    assert result is None


def test_missing_start_time_returns_none():
    p = _make_path("2025-03-15_09.00.00-running.fit")
    with _patch_fitparse([_mock_session({"start_time": None})]):
        result = parse_fit_file(p)
    assert result is None


# ---------------------------------------------------------------------------
# Normal parse
# ---------------------------------------------------------------------------

def test_normal_parse_all_fields():
    p = _make_path("2025-03-15_09.00.00-running.fit")
    with _patch_fitparse([_mock_session()]):
        result = parse_fit_file(p)

    assert result is not None
    assert result["total_duration"] == 3600
    assert result["total_distance"] == 10000.0
    assert result["total_ascent"] == 250.0
    assert result["calories"] == 650
    assert result["hr_avg"] == 148
    assert result["hr_max"] == 172
    assert result["hr_min"] == 98
    assert result["hr_zone_1"] == 600.0
    assert result["hr_zone_2"] == 1200.0
    assert result["hr_zone_3"] == 900.0
    assert result["hr_zone_4"] == 600.0
    assert result["hr_zone_5"] == 300.0


def test_recorded_at_is_utc_aware():
    p = _make_path("2025-03-15_09.00.00-running.fit")
    with _patch_fitparse([_mock_session()]):
        result = parse_fit_file(p)
    assert result["recorded_at"].tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# Missing optional fields
# ---------------------------------------------------------------------------

def test_missing_optional_fields_are_none():
    p = _make_path("2025-03-15_09.00.00-yoga.fit")
    sparse = _mock_session({
        "total_distance": None,
        "total_ascent": None,
        "total_calories": None,
        "avg_heart_rate": None,
        "max_heart_rate": None,
        "min_heart_rate": None,
        "time_in_hr_zone": None,
    })
    with _patch_fitparse([sparse]):
        result = parse_fit_file(p)

    assert result is not None
    assert result["total_distance"] is None
    assert result["hr_avg"] is None
    assert result["hr_zone_1"] is None


def test_short_hr_zone_array_fills_missing_zones_with_none():
    p = _make_path("2025-03-15_09.00.00-running.fit")
    with _patch_fitparse([_mock_session({"time_in_hr_zone": [600.0, 1200.0]})]):
        result = parse_fit_file(p)
    assert result["hr_zone_1"] == 600.0
    assert result["hr_zone_2"] == 1200.0
    assert result["hr_zone_3"] is None
    assert result["hr_zone_4"] is None
    assert result["hr_zone_5"] is None


# ---------------------------------------------------------------------------
# Exception during parse
# ---------------------------------------------------------------------------

def test_fitparse_exception_returns_none():
    p = _make_path("2025-03-15_09.00.00-running.fit")
    with patch("app.ingestion.fit_parser.fitparse.FitFile", side_effect=Exception("corrupt file")):
        result = parse_fit_file(p)
    assert result is None
