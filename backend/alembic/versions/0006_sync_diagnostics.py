"""Expose FreshRSS synchronization failures without exposing credentials."""
import sqlalchemy as sa
from alembic import op

revision = "0006_sync_diagnostics"
down_revision = "0005_ai_execution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("freshrss_connections", sa.Column("last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("freshrss_connections", "last_error")
