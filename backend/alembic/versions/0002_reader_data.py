"""reader data

Revision ID: 0002_reader_data
Revises: 0001_phase_0
Create Date: 2026-08-03
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_reader_data"
down_revision = "0001_phase_0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid_type = sa.Uuid()
    op.create_table("folders", sa.Column("id", uuid_type, primary_key=True), sa.Column("freshrss_folder_id", sa.String(255), unique=True), sa.Column("name", sa.String(512), nullable=False))
    op.create_table("feeds", sa.Column("id", uuid_type, primary_key=True), sa.Column("freshrss_feed_id", sa.String(255), unique=True), sa.Column("title", sa.String(512), nullable=False), sa.Column("feed_url", sa.Text()), sa.Column("site_url", sa.Text()), sa.Column("folder_id", uuid_type, sa.ForeignKey("folders.id")))
    op.create_table("entries", sa.Column("id", uuid_type, primary_key=True), sa.Column("freshrss_entry_id", sa.String(255), unique=True), sa.Column("feed_id", uuid_type, sa.ForeignKey("feeds.id"), nullable=False), sa.Column("title", sa.String(2048), nullable=False), sa.Column("url", sa.Text()), sa.Column("canonical_url", sa.Text()), sa.Column("author", sa.String(512)), sa.Column("published_at", sa.DateTime(timezone=True), nullable=False), sa.Column("content_html", sa.Text()), sa.Column("content_text", sa.Text()), sa.Column("content_hash", sa.String(64), nullable=False), sa.Column("language", sa.String(32)), sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("is_starred", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("ix_entries_feed_id", "entries", ["feed_id"])
    op.create_index("ix_entries_published_at", "entries", ["published_at"])
    op.create_index("ix_entries_content_hash", "entries", ["content_hash"])
    op.create_index("ix_entries_is_read", "entries", ["is_read"])
    op.create_index("ix_entries_is_starred", "entries", ["is_starred"])
    op.create_table("reading_positions", sa.Column("entry_id", uuid_type, sa.ForeignKey("entries.id"), primary_key=True), sa.Column("scroll_ratio", sa.Float(), nullable=False, server_default="0"), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))


def downgrade() -> None:
    op.drop_table("reading_positions")
    op.drop_index("ix_entries_is_starred", table_name="entries")
    op.drop_index("ix_entries_is_read", table_name="entries")
    op.drop_index("ix_entries_content_hash", table_name="entries")
    op.drop_index("ix_entries_published_at", table_name="entries")
    op.drop_index("ix_entries_feed_id", table_name="entries")
    op.drop_table("entries")
    op.drop_table("feeds")
    op.drop_table("folders")
