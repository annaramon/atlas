import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

log = logging.getLogger(__name__)


def iter_ndjson(path: Path) -> Iterator[dict]:
    """Yield each parsed JSON line from an NDJSON file, skipping blank/malformed lines."""
    with path.open() as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                log.warning("Bad JSON on line %d of %s", line_num, path.name)


def _to_utc(ts_str: str) -> datetime:
    return datetime.fromisoformat(ts_str).astimezone(timezone.utc)


def parse_sleep_line(row: dict, hr_rest: int) -> dict | None:
    """Parse one NDJSON sleep row.

    Returns a dict matching the Sleep model columns plus '_bedtime_end' (a
    datetime used for stage linking in the pipeline — strip before inserting).

    Sleep HR fields (hrAvg, hrMin) are stored as fractions relative to hrRest
    (e.g. 0.9 means 0.9 * hrRest). Multiply by hr_rest to get bpm.
    Note: CLAUDE.md incorrectly states these are fractions of hrMax — using
    hrMax produces physiologically impossible values (178-221 bpm during sleep).
    """
    try:
        ts = _to_utc(row['timestamp'])
        e = row['entryData']

        hr_avg_raw = e.get('hrAvg')
        hr_min_raw = e.get('hrMin')
        bedtime_end_str = e.get('bedtimeEnd')

        return {
            'recorded_at': ts,
            'sleep_id': str(e['sleepId']) if e.get('sleepId') is not None else None,
            'deep_duration': int(e['deepSleepDuration']) if e.get('deepSleepDuration') is not None else None,
            'light_duration': int(e['lightSleepDuration']) if e.get('lightSleepDuration') is not None else None,
            'rem_duration': int(e['remSleepDuration']) if e.get('remSleepDuration') is not None else None,
            'hr_avg': round(hr_avg_raw * hr_rest) if hr_avg_raw is not None else None,
            'hr_min': round(hr_min_raw * hr_rest) if hr_min_raw is not None else None,
            'hrv': e.get('avgHrv'),
            'spo2_avg': e.get('maxSpo2'),
            'quality_score': e.get('quality'),
            # Not a model column — used in pipeline to match stages, stripped before insert
            '_bedtime_end': _to_utc(bedtime_end_str) if bedtime_end_str else None,
        }
    except (KeyError, ValueError) as exc:
        log.warning("Skipping malformed sleep line: %s", exc)
        return None


def parse_sleep_stage_line(row: dict) -> dict | None:
    """Parse one NDJSON sleep_stages row.

    Returns a dict with 'recorded_at', 'stage' (lowercased), and 'duration'.
    The 'sleep_id' FK is resolved by the pipeline via timestamp containment.
    """
    try:
        ts = _to_utc(row['timestamp'])
        e = row['entryData']
        return {
            'recorded_at': ts,
            'stage': e['stage'].lower(),
            'duration': int(e['duration']),
        }
    except (KeyError, ValueError) as exc:
        log.warning("Skipping malformed sleep_stage line: %s", exc)
        return None


def parse_activity_line(row: dict) -> dict | None:
    try:
        ts = _to_utc(row['timestamp'])
        e = row['entryData']
        return {
            'recorded_at': ts,
            'step_count': e.get('stepCount'),
            'energy_consumption': e.get('energyConsumption'),
        }
    except (KeyError, ValueError) as exc:
        log.warning("Skipping malformed activity line: %s", exc)
        return None


def parse_recovery_line(row: dict) -> dict | None:
    try:
        ts = _to_utc(row['timestamp'])
        e = row['entryData']
        return {
            'recorded_at': ts,
            'balance': e.get('balance'),
            'stress_state': e.get('stressState'),
        }
    except (KeyError, ValueError) as exc:
        log.warning("Skipping malformed recovery line: %s", exc)
        return None
