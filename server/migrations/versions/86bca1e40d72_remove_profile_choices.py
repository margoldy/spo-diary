"""предпочтения только из записей библиотеки"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

revision = "86bca1e40d72"
down_revision = "75ad152fc932"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    users = list(connection.scalars(sa.text("SELECT DISTINCT user_id FROM user_tags WHERE choice IS NOT NULL")))
    op.drop_column("user_tags", "weight")
    op.drop_constraint(op.f("ck_user_tags_choice"), "user_tags", type_="check")
    op.drop_column("user_tags", "choice")
    op.add_column(
        "user_tags",
        sa.Column(
            "weight", sa.Numeric(),
            sa.Computed("(positive-negative)/(2+positive+negative)", persisted=True), nullable=False,
        ),
    )
    connection.execute(sa.text("DELETE FROM user_tags WHERE positive=0 AND negative=0"))
    if users:
        from app.db.queries.preferences import PreferencesQueries

        with Session(bind=connection) as db:
            for user_id in users:
                PreferencesQueries(db).rescore(user_id)
            db.flush()


def downgrade():
    op.drop_column("user_tags", "weight")
    op.add_column("user_tags", sa.Column("choice", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(op.f("ck_user_tags_choice"), "user_tags", "choice IN (-1,1)")
    op.add_column(
        "user_tags",
        sa.Column(
            "weight", sa.Numeric(),
            sa.Computed(
                "(positive-negative+0.5*coalesce(choice,0))/(2+positive+negative+abs(0.5*coalesce(choice,0)))",
                persisted=True,
            ),
            nullable=False,
        ),
    )
