import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import cast, Date, func

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.activity import Activity
from app.models.recovery import Recovery
from app.models.sleep import Sleep
from app.models.workout import Workout


def _parse_date(date_str: str) -> datetime:
    return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)


def get_workout_summary(start_date: str, end_date: str, sport_type: str | None = None) -> list[dict]:
    """Return workouts between start_date and end_date (ISO dates, inclusive)."""
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    with SessionLocal() as db:
        q = db.query(Workout).filter(Workout.recorded_at >= start, Workout.recorded_at <= end)
        if sport_type:
            q = q.filter(Workout.sport_type == sport_type)
        rows = q.order_by(Workout.recorded_at).all()

    return [
        {
            "date": r.recorded_at.date().isoformat(),
            "sport_type": r.sport_type,
            "duration_seconds": r.total_duration,
            "distance_meters": r.total_distance,
            "ascent_meters": r.total_ascent,
            "calories": r.calories,
            "hr_avg": r.hr_avg,
            "hr_max": r.hr_max,
            "hr_min": r.hr_min,
            "hr_zone_1_seconds": r.hr_zone_1,
            "hr_zone_2_seconds": r.hr_zone_2,
            "hr_zone_3_seconds": r.hr_zone_3,
            "hr_zone_4_seconds": r.hr_zone_4,
            "hr_zone_5_seconds": r.hr_zone_5,
        }
        for r in rows
    ]


def get_sleep_summary(start_date: str, end_date: str) -> list[dict]:
    """Return sleep sessions between start_date and end_date (ISO dates, inclusive)."""
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    with SessionLocal() as db:
        rows = (
            db.query(Sleep)
            .filter(Sleep.recorded_at >= start, Sleep.recorded_at <= end)
            .order_by(Sleep.recorded_at)
            .all()
        )

    return [
        {
            "date": r.recorded_at.date().isoformat(),
            "deep_duration_seconds": r.deep_duration,
            "light_duration_seconds": r.light_duration,
            "rem_duration_seconds": r.rem_duration,
            "hr_avg_bpm": r.hr_avg,
            "hr_min_bpm": r.hr_min,
            "hrv": r.hrv,
            "spo2_avg": r.spo2_avg,
            "quality_score": r.quality_score,
        }
        for r in rows
    ]


def get_activity_summary(start_date: str, end_date: str) -> list[dict]:
    """Return daily step and energy totals between start_date and end_date (ISO dates, inclusive).

    Activity is stored as 30-min slots — this aggregates them into daily totals at query time.
    """
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    with SessionLocal() as db:
        rows = (
            db.query(
                cast(Activity.recorded_at, Date).label("day"),
                func.sum(Activity.step_count).label("total_steps"),
                func.sum(Activity.energy_consumption).label("total_energy_kcal"),
            )
            .filter(Activity.recorded_at >= start, Activity.recorded_at <= end)
            .group_by("day")
            .order_by("day")
            .all()
        )

    return [
        {
            "date": r.day.isoformat(),
            "total_steps": r.total_steps,
            "total_energy_kcal": r.total_energy_kcal,
        }
        for r in rows
    ]


def get_recovery_summary(start_date: str, end_date: str) -> list[dict]:
    """Return recovery balance and stress state between start_date and end_date (ISO dates, inclusive)."""
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    with SessionLocal() as db:
        rows = (
            db.query(Recovery)
            .filter(Recovery.recorded_at >= start, Recovery.recorded_at <= end)
            .order_by(Recovery.recorded_at)
            .all()
        )

    return [
        {
            "date": r.recorded_at.date().isoformat(),
            "balance": r.balance,
            "stress_state": r.stress_state,
        }
        for r in rows
    ]


def get_user_profile() -> dict:
    """Return static user profile data (hrMax, hrRest, weight, etc.) from the export directory."""
    profile_path = Path(settings.export_dir) / "user" / "user.json"
    data = json.loads(profile_path.read_text())
    return {
        "hr_max": data.get("hrMax"),
        "hr_rest": data.get("hrRest"),
        "weight_kg": data.get("weight"),
        "height_cm": data.get("height"),
        "date_of_birth": data.get("dateOfBirth"),
        "gender": data.get("gender"),
    }


# ---------------------------------------------------------------------------
# Ollama tool schemas
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_workout_summary",
            "description": "Get workouts over a date range, optionally filtered by sport type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start date in ISO format, e.g. 2026-04-01"},
                    "end_date":   {"type": "string", "description": "End date in ISO format, e.g. 2026-04-10"},
                    "sport_type": {"type": "string", "description": "Optional sport type slug, e.g. running, cross_country_skiing"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sleep_summary",
            "description": "Get sleep metrics (deep/light/REM durations, HRV, SpO2, quality score) over a date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start date in ISO format, e.g. 2026-04-01"},
                    "end_date":   {"type": "string", "description": "End date in ISO format, e.g. 2026-04-10"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_activity_summary",
            "description": "Get daily step count and energy expenditure totals over a date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start date in ISO format, e.g. 2026-04-01"},
                    "end_date":   {"type": "string", "description": "End date in ISO format, e.g. 2026-04-10"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recovery_summary",
            "description": "Get recovery balance (0–1) and stress state over a date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start date in ISO format, e.g. 2026-04-01"},
                    "end_date":   {"type": "string", "description": "End date in ISO format, e.g. 2026-04-10"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_profile",
            "description": "Get the athlete's static profile: hrMax, hrRest, weight, height, date of birth, gender.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

# Maps tool name → callable, used by the agent loop to dispatch tool calls
TOOL_DISPATCH: dict[str, callable] = {
    "get_workout_summary": get_workout_summary,
    "get_sleep_summary": get_sleep_summary,
    "get_activity_summary": get_activity_summary,
    "get_recovery_summary": get_recovery_summary,
    "get_user_profile": get_user_profile,
}
