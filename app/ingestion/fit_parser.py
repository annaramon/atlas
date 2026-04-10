import logging
from datetime import timezone
from pathlib import Path

import fitparse

log = logging.getLogger(__name__)


def parse_fit_file(path: Path) -> dict | None:
    """Parse a FIT file and return a dict matching the Workout model columns.

    Returns None if the file cannot be parsed or has no session message.
    Sport type and start timestamp are taken from the filename, which is more
    reliable than the FIT session sport field (e.g. gym files report 'training').
    """
    filename = path.name  # 2024-12-27_10.26.13-cross_country_skiing.fit

    try:
        stem = path.stem  # 2024-12-27_10.26.13-cross_country_skiing
        _, rest = stem.split('_', 1)   # rest = 10.26.13-cross_country_skiing
        _, sport_type = rest.split('-', 1)
    except ValueError:
        log.warning("Could not parse filename: %s", filename)
        return None

    try:
        fit = fitparse.FitFile(str(path))
        sessions = list(fit.get_messages('session'))
        if not sessions:
            log.warning("No session message in %s", filename)
            return None

        msg = sessions[0]

        def get(field):
            return msg.get_value(field)

        start_time = get('start_time')
        if start_time is None:
            log.warning("No start_time in %s", filename)
            return None

        # fitparse returns naive datetimes in UTC
        recorded_at = start_time.replace(tzinfo=timezone.utc)

        duration_raw = get('total_timer_time')
        hr_zones = get('time_in_hr_zone')

        def zone(i):
            return hr_zones[i] if hr_zones and len(hr_zones) > i else None

        return {
            'recorded_at': recorded_at,
            'sport_type': sport_type,
            'source_file': filename,
            'total_duration': int(duration_raw) if duration_raw is not None else None,
            'total_distance': get('total_distance'),
            'total_ascent': get('total_ascent'),
            'calories': get('total_calories'),
            'hr_avg': get('avg_heart_rate'),
            'hr_max': get('max_heart_rate'),
            'hr_min': get('min_heart_rate'),
            'hr_zone_1': zone(0),
            'hr_zone_2': zone(1),
            'hr_zone_3': zone(2),
            'hr_zone_4': zone(3),
            'hr_zone_5': zone(4),
        }

    except Exception as exc:
        log.warning("Failed to parse %s: %s", filename, exc)
        return None
