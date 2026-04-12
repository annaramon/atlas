import json
import textwrap
from pathlib import Path

import pytest

from app.ingestion.ndjson_parser import (
    iter_ndjson,
    parse_activity_line,
    parse_recovery_line,
    parse_sleep_line,
    parse_sleep_stage_line,
)

HR_REST = 55


# ---------------------------------------------------------------------------
# parse_sleep_line
# ---------------------------------------------------------------------------

def _sleep_row(overrides: dict = {}) -> dict:
    base = {
        "timestamp": "2025-10-01T22:00:00+00:00",
        "entryData": {
            "sleepId": 123,
            "deepSleepDuration": 3600,
            "lightSleepDuration": 7200,
            "remSleepDuration": 5400,
            "hrAvg": 0.90,
            "hrMin": 0.80,
            "avgHrv": 42.5,
            "maxSpo2": 0.97,
            "quality": 0.85,
            "bedtimeEnd": "2025-10-02T06:00:00+00:00",
        },
    }
    base["entryData"].update(overrides.get("entryData", {}))
    return {**base, **{k: v for k, v in overrides.items() if k != "entryData"}}


def test_parse_sleep_line_normal():
    result = parse_sleep_line(_sleep_row(), HR_REST)
    assert result is not None
    assert result["deep_duration"] == 3600
    assert result["light_duration"] == 7200
    assert result["rem_duration"] == 5400
    assert result["hrv"] == 42.5
    assert result["spo2_avg"] == 0.97
    assert result["quality_score"] == 0.85
    assert result["sleep_id"] == "123"


def test_parse_sleep_line_hr_normalized_by_hr_rest():
    result = parse_sleep_line(_sleep_row(), HR_REST)
    assert result["hr_avg"] == round(0.90 * HR_REST)
    assert result["hr_min"] == round(0.80 * HR_REST)


def test_parse_sleep_line_bedtime_end_parsed():
    result = parse_sleep_line(_sleep_row(), HR_REST)
    assert result["_bedtime_end"] is not None
    assert result["_bedtime_end"].isoformat().startswith("2025-10-02")


def test_parse_sleep_line_missing_optional_fields():
    row = _sleep_row({"entryData": {"hrAvg": None, "hrMin": None, "bedtimeEnd": None}})
    # Remove optional keys entirely
    for key in ("hrAvg", "hrMin", "bedtimeEnd", "avgHrv", "maxSpo2", "quality"):
        row["entryData"].pop(key, None)
    result = parse_sleep_line(row, HR_REST)
    assert result is not None
    assert result["hr_avg"] is None
    assert result["hr_min"] is None
    assert result["_bedtime_end"] is None


def test_parse_sleep_line_malformed_returns_none():
    result = parse_sleep_line({"bad": "data"}, HR_REST)
    assert result is None


def test_parse_sleep_line_timestamp_normalized_to_utc():
    row = _sleep_row({"timestamp": "2025-10-01T23:00:00+01:00"})
    result = parse_sleep_line(row, HR_REST)
    assert result["recorded_at"].utcoffset().total_seconds() == 0
    assert result["recorded_at"].hour == 22  # +01:00 → UTC


# ---------------------------------------------------------------------------
# parse_sleep_stage_line
# ---------------------------------------------------------------------------

def test_parse_sleep_stage_line_normal():
    row = {"timestamp": "2025-10-01T22:30:00+00:00", "entryData": {"stage": "DEEP", "duration": 900}}
    result = parse_sleep_stage_line(row)
    assert result is not None
    assert result["stage"] == "deep"
    assert result["duration"] == 900


def test_parse_sleep_stage_line_malformed_returns_none():
    assert parse_sleep_stage_line({"bad": "data"}) is None


# ---------------------------------------------------------------------------
# parse_activity_line
# ---------------------------------------------------------------------------

def test_parse_activity_line_normal():
    row = {"timestamp": "2024-12-01T08:00:00+00:00", "entryData": {"stepCount": 500, "energyConsumption": 45.2}}
    result = parse_activity_line(row)
    assert result is not None
    assert result["step_count"] == 500
    assert result["energy_consumption"] == 45.2


def test_parse_activity_line_missing_fields_returns_none_values():
    row = {"timestamp": "2024-12-01T08:00:00+00:00", "entryData": {}}
    result = parse_activity_line(row)
    assert result is not None
    assert result["step_count"] is None
    assert result["energy_consumption"] is None


def test_parse_activity_line_malformed_returns_none():
    assert parse_activity_line({"bad": "data"}) is None


# ---------------------------------------------------------------------------
# parse_recovery_line
# ---------------------------------------------------------------------------

def test_parse_recovery_line_normal():
    row = {"timestamp": "2025-09-01T07:00:00+00:00", "entryData": {"balance": 0.72, "stressState": 2}}
    result = parse_recovery_line(row)
    assert result is not None
    assert result["balance"] == 0.72
    assert result["stress_state"] == 2


def test_parse_recovery_line_malformed_returns_none():
    assert parse_recovery_line({"bad": "data"}) is None


# ---------------------------------------------------------------------------
# iter_ndjson
# ---------------------------------------------------------------------------

def test_iter_ndjson_parses_valid_lines(tmp_path):
    f = tmp_path / "test.ndjson"
    f.write_text('{"a": 1}\n{"b": 2}\n')
    result = list(iter_ndjson(f))
    assert result == [{"a": 1}, {"b": 2}]


def test_iter_ndjson_skips_blank_lines(tmp_path):
    f = tmp_path / "test.ndjson"
    f.write_text('{"a": 1}\n\n{"b": 2}\n')
    result = list(iter_ndjson(f))
    assert len(result) == 2


def test_iter_ndjson_skips_malformed_lines(tmp_path):
    f = tmp_path / "test.ndjson"
    f.write_text('{"a": 1}\nnot json\n{"b": 2}\n')
    result = list(iter_ndjson(f))
    assert result == [{"a": 1}, {"b": 2}]
