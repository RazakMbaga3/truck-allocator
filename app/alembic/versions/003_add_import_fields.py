"""Add dispatch_date and upload_date to truck_schedules.

Revision ID: 003
Revises: 002
Create Date: 2026-05-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("truck_schedules", sa.Column("dispatch_date", sa.DateTime, nullable=True))
    op.add_column("truck_schedules", sa.Column("upload_date",   sa.DateTime, nullable=True))


def downgrade() -> None:
    op.drop_column("truck_schedules", "dispatch_date")
    op.drop_column("truck_schedules", "upload_date")
