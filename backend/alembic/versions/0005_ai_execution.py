"""AI task inputs and automatic processing flags."""
import sqlalchemy as sa
from alembic import op
revision="0005_ai_execution"; down_revision="0004_ai_platform"; branch_labels=None; depends_on=None
def upgrade() -> None:
 op.create_table("ai_job_entries",sa.Column("job_id",sa.Uuid(),sa.ForeignKey("ai_jobs.id"),primary_key=True),sa.Column("entry_id",sa.Uuid(),sa.ForeignKey("entries.id"),primary_key=True),sa.Column("status",sa.String(32),server_default="queued"),sa.Column("intermediate_result_json",sa.Text()))
 op.add_column("feeds",sa.Column("auto_translate_override",sa.Boolean()))
 op.add_column("feeds",sa.Column("auto_summary_override",sa.Boolean()))
def downgrade() -> None:
 op.drop_column("feeds","auto_summary_override");op.drop_column("feeds","auto_translate_override");op.drop_table("ai_job_entries")
