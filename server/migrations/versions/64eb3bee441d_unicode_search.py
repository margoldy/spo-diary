"""поиск по unicode"""

import sqlalchemy as sa
from alembic import op

revision = "64eb3bee441d"
down_revision = "9b1017657e36"
branch_labels = None
depends_on = None


def upgrade():
    for table, column in [
        ("works", "title"),
        ("private_works", "title"),
        ("tags", "name"),
        ("genres", "name"),
        ("types", "name"),
    ]:
        op.alter_column(table, column, existing_type=sa.Text(), type_=sa.Text(collation="und-x-icu"))


def downgrade():
    for table, column in [
        ("works", "title"),
        ("private_works", "title"),
        ("tags", "name"),
        ("genres", "name"),
        ("types", "name"),
    ]:
        op.alter_column(table, column, existing_type=sa.Text(collation="und-x-icu"), type_=sa.Text(collation="default"))
