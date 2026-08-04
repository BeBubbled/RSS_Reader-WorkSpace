"""FreshRSS connection and scoped external IDs."""
import sqlalchemy as sa
from alembic import op
revision = "0003_freshrss_sync"; down_revision = "0002_reader_data"; branch_labels = None; depends_on = None
def upgrade() -> None:
    uuid_type = sa.Uuid()
    op.create_table("freshrss_connections", sa.Column("id", uuid_type, primary_key=True), sa.Column("base_url", sa.Text(), nullable=False), sa.Column("username", sa.String(512), nullable=False), sa.Column("encrypted_api_password", sa.Text(), nullable=False), sa.Column("sync_interval", sa.Integer(), nullable=False, server_default="900"), sa.Column("last_sync_at", sa.DateTime(timezone=True)), sa.Column("status", sa.String(64), nullable=False, server_default="not_synced"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    for table in ("folders", "feeds", "entries"): op.add_column(table, sa.Column("connection_id", uuid_type, sa.ForeignKey("freshrss_connections.id")))
    op.drop_constraint("folders_freshrss_folder_id_key", "folders", type_="unique")
    op.drop_constraint("feeds_freshrss_feed_id_key", "feeds", type_="unique")
    op.drop_constraint("entries_freshrss_entry_id_key", "entries", type_="unique")
    op.create_unique_constraint("uq_entries_connection_freshrss_id", "entries", ["connection_id", "freshrss_entry_id"])
def downgrade() -> None:
    op.drop_constraint("uq_entries_connection_freshrss_id", "entries", type_="unique")
    for table in ("entries", "feeds", "folders"): op.drop_column(table, "connection_id")
    op.drop_table("freshrss_connections")
