"""add unique constraint to sleep_stages

Revision ID: a1c3e2f9b847
Revises: 764152f072c2
Create Date: 2026-04-09 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a1c3e2f9b847'
down_revision: Union[str, None] = '764152f072c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_sleep_stage_sleep_id_recorded_at',
        'sleep_stages',
        ['sleep_id', 'recorded_at'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_sleep_stage_sleep_id_recorded_at',
        'sleep_stages',
        type_='unique',
    )
