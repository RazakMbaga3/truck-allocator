"""Add manual truck allocation tables.

Revision ID: 002
Revises: 001
Create Date: 2026-05-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "truck_allocations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "schedule_id",
            sa.Integer,
            sa.ForeignKey("truck_schedules.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, default="DRAFT"),
        sa.Column("remarks", sa.Text, nullable=True),
        sa.Column("released_at", sa.DateTime, nullable=True),
        sa.Column("loaded_at", sa.DateTime, nullable=True),
        sa.Column("released_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_truck_allocations_schedule_id", "truck_allocations", ["schedule_id"])
    op.create_index("ix_truck_allocations_status", "truck_allocations", ["status"])

    op.create_table(
        "allocation_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "allocation_id",
            sa.Integer,
            sa.ForeignKey("truck_allocations.id"),
            nullable=False,
        ),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("order_ref", sa.String(50), nullable=False),
        sa.Column("order_date", sa.Date, nullable=True),
        sa.Column("product", sa.String(200), nullable=False),
        sa.Column("quantity_tonnes", sa.Float, nullable=False),
        sa.Column("destination_location", sa.String(200), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("sequence", sa.Integer, default=1, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_allocation_items_allocation_id", "allocation_items", ["allocation_id"])


def downgrade() -> None:
    op.drop_table("allocation_items")
    op.drop_table("truck_allocations")
