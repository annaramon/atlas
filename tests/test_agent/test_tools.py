import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.agent.tools import (
    get_activity_summary,
    get_recovery_summary,
    get_sleep_summary,
    get_user_profile,
    get_workout_summary,
)
from app.models.activity import Activity
from app.models.recovery import Recovery
from app.models.sleep import Sleep
from app.models.workout import Workout


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# get_workout_summary
# ---------------------------------------------------------------------------

def test_get_workout_summary_returns_workouts_in_range(patched_db):
    patched_db.add(Workout(
        recorded_at=_dt("2026-03-10T09:00:00"),
        sport_type="running",
        source_file="2026-03-10_09.00.00-running.fit",
        total_duration=3600,
        total_distance=10000.0,
        hr_avg=148,
    ))
    patched_db.commit()

    result = get_workout_summary("2026-03-01", "2026-03-31")
    assert len(result) == 1
    assert result[0]["sport_type"] == "running"
    assert result[0]["duration_seconds"] == 3600
    assert result[0]["distance_meters"] == 10000.0
    assert result[0]["hr_avg"] == 148


def test_get_workout_summary_excludes_out_of_range(patched_db):
    patched_db.add(Workout(
        recorded_at=_dt("2026-01-05T09:00:00"),
        sport_type="running",
        source_file="old.fit",
    ))
    patched_db.commit()

    result = get_workout_summary("2026-03-01", "2026-03-31")
    assert result == []


def test_get_workout_summary_filters_by_sport_type(patched_db):
    patched_db.add_all([
        Workout(recorded_at=_dt("2026-03-10T09:00:00"), sport_type="running", source_file="a.fit"),
        Workout(recorded_at=_dt("2026-03-11T10:00:00"), sport_type="cycling", source_file="b.fit"),
    ])
    patched_db.commit()

    result = get_workout_summary("2026-03-01", "2026-03-31", sport_type="running")
    assert len(result) == 1
    assert result[0]["sport_type"] == "running"


def test_get_workout_summary_date_field_is_iso(patched_db):
    patched_db.add(Workout(
        recorded_at=_dt("2026-03-10T09:00:00"),
        sport_type="running",
        source_file="x.fit",
    ))
    patched_db.commit()

    result = get_workout_summary("2026-03-01", "2026-03-31")
    assert result[0]["date"] == "2026-03-10"


# ---------------------------------------------------------------------------
# get_sleep_summary
# ---------------------------------------------------------------------------

def test_get_sleep_summary_returns_sessions_in_range(patched_db):
    patched_db.add(Sleep(
        recorded_at=_dt("2026-03-10T22:00:00"),
        deep_duration=3600,
        light_duration=7200,
        rem_duration=5400,
        hr_avg=52,
        hrv=44.0,
        quality_score=0.82,
    ))
    patched_db.commit()

    result = get_sleep_summary("2026-03-01", "2026-03-31")
    assert len(result) == 1
    assert result[0]["deep_duration_seconds"] == 3600
    assert result[0]["hr_avg_bpm"] == 52
    assert result[0]["quality_score"] == 0.82


def test_get_sleep_summary_excludes_out_of_range(patched_db):
    patched_db.add(Sleep(recorded_at=_dt("2026-01-01T22:00:00")))
    patched_db.commit()

    result = get_sleep_summary("2026-03-01", "2026-03-31")
    assert result == []


# ---------------------------------------------------------------------------
# get_activity_summary
# ---------------------------------------------------------------------------

def test_get_activity_summary_aggregates_daily(patched_db):
    # Two 30-min slots on the same day
    patched_db.add_all([
        Activity(recorded_at=_dt("2026-03-10T08:00:00"), step_count=1000, energy_consumption=80.0),
        Activity(recorded_at=_dt("2026-03-10T08:30:00"), step_count=1200, energy_consumption=90.0),
    ])
    patched_db.commit()

    result = get_activity_summary("2026-03-01", "2026-03-31")
    assert len(result) == 1
    assert result[0]["total_steps"] == 2200
    assert abs(result[0]["total_energy_kcal"] - 170.0) < 0.01


def test_get_activity_summary_groups_by_day(patched_db):
    patched_db.add_all([
        Activity(recorded_at=_dt("2026-03-10T08:00:00"), step_count=1000, energy_consumption=80.0),
        Activity(recorded_at=_dt("2026-03-11T08:00:00"), step_count=2000, energy_consumption=100.0),
    ])
    patched_db.commit()

    result = get_activity_summary("2026-03-01", "2026-03-31")
    assert len(result) == 2
    dates = [r["date"] for r in result]
    assert "2026-03-10" in dates
    assert "2026-03-11" in dates


def test_get_activity_summary_excludes_out_of_range(patched_db):
    patched_db.add(Activity(recorded_at=_dt("2026-01-01T08:00:00"), step_count=5000))
    patched_db.commit()

    result = get_activity_summary("2026-03-01", "2026-03-31")
    assert result == []


# ---------------------------------------------------------------------------
# get_recovery_summary
# ---------------------------------------------------------------------------

def test_get_recovery_summary_returns_data_in_range(patched_db):
    patched_db.add(Recovery(
        recorded_at=_dt("2026-03-10T07:00:00"),
        balance=0.75,
        stress_state=2,
    ))
    patched_db.commit()

    result = get_recovery_summary("2026-03-01", "2026-03-31")
    assert len(result) == 1
    assert result[0]["balance"] == 0.75
    assert result[0]["stress_state"] == 2


def test_get_recovery_summary_excludes_out_of_range(patched_db):
    patched_db.add(Recovery(recorded_at=_dt("2026-01-01T07:00:00"), balance=0.5))
    patched_db.commit()

    result = get_recovery_summary("2026-03-01", "2026-03-31")
    assert result == []


# ---------------------------------------------------------------------------
# get_user_profile
# ---------------------------------------------------------------------------

def test_get_user_profile_reads_json(tmp_path, monkeypatch):
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    (user_dir / "user.json").write_text(json.dumps({
        "hrMax": 198,
        "hrRest": 55,
        "weight": 65.0,
        "height": 168,
        "dateOfBirth": "1990-01-01",
        "gender": "female",
    }))

    monkeypatch.setattr("app.agent.tools.settings.export_dir", str(tmp_path))

    result = get_user_profile()
    assert result["hr_max"] == 198
    assert result["hr_rest"] == 55
    assert result["weight_kg"] == 65.0
    assert result["gender"] == "female"
