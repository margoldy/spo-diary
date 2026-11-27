"""основные признаки произведений"""

import sqlalchemy as sa
from alembic import op

revision = "75ad152fc932"
down_revision = "64eb3bee441d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("work_tags", sa.Column("is_main", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    op.drop_column("work_tags", "is_main")
