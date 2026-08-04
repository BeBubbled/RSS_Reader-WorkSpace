"""phase 0 baseline

Revision ID: 0001_phase_0
Revises:
Create Date: 2026-08-03
"""

revision = "0001_phase_0"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Establish the Alembic version chain; domain tables begin in Phase 1."""


def downgrade() -> None:
    """The baseline does not create domain objects."""
