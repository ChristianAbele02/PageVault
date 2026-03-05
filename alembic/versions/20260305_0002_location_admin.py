"""Add location fields and admin events

Revision ID: 20260305_0002
Revises: 20260305_0001
Create Date: 2026-03-05
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260305_0002"
down_revision = "20260305_0001"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "books", "location_type"):
        op.add_column(
            "books",
            sa.Column("location_type", sa.Text(), nullable=False, server_default="shelf"),
        )
    if not _has_column(inspector, "books", "location_note"):
        op.add_column("books", sa.Column("location_note", sa.Text(), nullable=True))
    if not _has_column(inspector, "books", "loan_person"):
        op.add_column("books", sa.Column("loan_person", sa.Text(), nullable=True))

    if not _has_table(inspector, "admin_events"):
        op.create_table(
            "admin_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("event_type", sa.Text(), nullable=False),
            sa.Column("details_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.Text(), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "admin_events"):
        op.drop_table("admin_events")

    if _has_column(inspector, "books", "loan_person"):
        op.drop_column("books", "loan_person")
    if _has_column(inspector, "books", "location_note"):
        op.drop_column("books", "location_note")
    if _has_column(inspector, "books", "location_type"):
        op.drop_column("books", "location_type")
