"""Baseline revision

Revision ID: 20260305_0001
Revises:
Create Date: 2026-03-05
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "20260305_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Baseline marker revision for projects that already have an initialized DB.
    pass


def downgrade() -> None:
    pass
