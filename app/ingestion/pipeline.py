"""Ingestion pipeline.

Usage:
    python -m app.ingestion.pipeline suunto-data-03042026
"""
import json
import logging
import sys
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.ingestion.fit_parser import parse_fit_file
from app.ingestion.ndjson_parser import (
    iter_ndjson,
    parse_activity_line,
    parse_recovery_line,
    parse_sleep_line,
    parse_sleep_stage_line,
)
from app.models.activity import Activity
from app.models.recovery import Recovery
from app.models.sleep import Sleep, SleepStage
from app.models.workout import Workout

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------

def _load_user_profile(export_dir: Path) -> dict:
    """Return {'hr_max': int, 'hr_rest': int} from user/user.json."""
    profile_path = export_dir / 'user' / 'user.json'
    try:
        data = json.loads(profile_path.read_text())
        profile = {'hr_max': int(data['hrMax']), 'hr_rest': int(data['hrRest'])}
        log.info("Loaded user profile: hrMax=%d hrRest=%d", profile['hr_max'], profile['hr_rest'])
        return profile
    except Exception as exc:
        log.warning("Could not load user profile (%s), using defaults hrMax=198 hrRest=60", exc)
        return {'hr_max': 198, 'hr_rest': 60}


# ---------------------------------------------------------------------------
# Workouts
# ---------------------------------------------------------------------------

def _ingest_workouts(export_dir: Path, db: Session) -> None:
    fit_files = sorted((export_dir / 'workouts').glob('*.fit'))
    log.info("Ingesting %d FIT files", len(fit_files))

    inserted = skipped = errors = 0
    for path in fit_files:
        row = parse_fit_file(path)
        if row is None:
            errors += 1
            continue
        result = db.execute(
            insert(Workout).values(**row).on_conflict_do_nothing(index_elements=['source_file'])
        )
        if result.rowcount:
            inserted += 1
        else:
            skipped += 1

    db.commit()
    log.info("Workouts: %d inserted, %d skipped (already existed), %d errors", inserted, skipped, errors)


# ---------------------------------------------------------------------------
# Sleep + sleep stages
# ---------------------------------------------------------------------------

def _load_all_stages(export_dir: Path) -> list[dict]:
    """Load and sort all sleep_stages rows from every monthly NDJSON file."""
    stages = []
    for path in sorted((export_dir / 'sleep_stages').glob('*.ndjson')):
        for row in iter_ndjson(path):
            parsed = parse_sleep_stage_line(row)
            if parsed:
                stages.append(parsed)
    stages.sort(key=lambda s: s['recorded_at'])
    log.info("Loaded %d sleep stage rows into memory", len(stages))
    return stages


def _stages_for_session(all_stages: list[dict], bedtime_start, bedtime_end) -> list[dict]:
    """Return stages whose recorded_at falls within [bedtime_start, bedtime_end)."""
    if bedtime_end is None:
        return []
    return [
        s for s in all_stages
        if bedtime_start <= s['recorded_at'] < bedtime_end
    ]


def _ingest_sleep(export_dir: Path, db: Session, hr_rest: int) -> None:
    all_stages = _load_all_stages(export_dir)

    sleep_inserted = sleep_skipped = stage_inserted = stage_skipped = 0

    for path in sorted((export_dir / 'sleep').glob('*.ndjson')):
        seen_recorded_at: set = set()

        for row in iter_ndjson(path):
            parsed = parse_sleep_line(row, hr_rest)
            if parsed is None:
                continue

            recorded_at = parsed['recorded_at']
            # Sleep NDJSON duplicates each session multiple times — deduplicate in-memory
            if recorded_at in seen_recorded_at:
                continue
            seen_recorded_at.add(recorded_at)

            bedtime_end = parsed.pop('_bedtime_end')

            result = db.execute(
                insert(Sleep).values(**parsed).on_conflict_do_nothing(index_elements=['recorded_at'])
            )

            if result.rowcount:
                sleep_inserted += 1
            else:
                sleep_skipped += 1

            # Resolve the sleep DB id (whether just inserted or already present)
            sleep_row = db.query(Sleep).filter(Sleep.recorded_at == recorded_at).one()

            # Insert matching stages
            matching = _stages_for_session(all_stages, recorded_at, bedtime_end)
            for stage in matching:
                res = db.execute(
                    insert(SleepStage)
                    .values(sleep_id=sleep_row.id, **stage)
                    .on_conflict_do_nothing(index_elements=['sleep_id', 'recorded_at'])
                )
                if res.rowcount:
                    stage_inserted += 1
                else:
                    stage_skipped += 1

        db.commit()
        log.info("Processed sleep file %s", path.name)

    log.info(
        "Sleep: %d sessions inserted, %d skipped | Stages: %d inserted, %d skipped",
        sleep_inserted, sleep_skipped, stage_inserted, stage_skipped,
    )


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------

def _ingest_activity(export_dir: Path, db: Session) -> None:
    inserted = skipped = 0

    for path in sorted((export_dir / 'activity').glob('*.ndjson')):
        for row in iter_ndjson(path):
            parsed = parse_activity_line(row)
            if parsed is None:
                continue
            result = db.execute(
                insert(Activity).values(**parsed).on_conflict_do_nothing(index_elements=['recorded_at'])
            )
            if result.rowcount:
                inserted += 1
            else:
                skipped += 1
        db.commit()

    log.info("Activity: %d inserted, %d skipped", inserted, skipped)


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------

def _ingest_recovery(export_dir: Path, db: Session) -> None:
    inserted = skipped = 0

    for path in sorted((export_dir / 'recovery').glob('*.ndjson')):
        for row in iter_ndjson(path):
            parsed = parse_recovery_line(row)
            if parsed is None:
                continue
            result = db.execute(
                insert(Recovery).values(**parsed).on_conflict_do_nothing(index_elements=['recorded_at'])
            )
            if result.rowcount:
                inserted += 1
            else:
                skipped += 1
        db.commit()

    log.info("Recovery: %d inserted, %d skipped", inserted, skipped)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(export_dir: Path, db: Session) -> None:
    log.info("Starting ingestion from %s", export_dir)
    profile = _load_user_profile(export_dir)
    _ingest_workouts(export_dir, db)
    _ingest_sleep(export_dir, db, profile['hr_rest'])
    _ingest_activity(export_dir, db)
    _ingest_recovery(export_dir, db)
    log.info("Ingestion complete")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

    if len(sys.argv) != 2:
        print("Usage: python -m app.ingestion.pipeline <export_dir>")
        sys.exit(1)

    export_dir = Path(sys.argv[1])
    if not export_dir.is_dir():
        print(f"Not a directory: {export_dir}")
        sys.exit(1)

    with SessionLocal() as db:
        run(export_dir, db)
