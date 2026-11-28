"""пересчёт рекомендаций с учётом содержания и типа"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

revision = "a713f8d9e602"
down_revision = "86bca1e40d72"
branch_labels = None
depends_on = None


def upgrade():
    from app.db.queries.library import LibraryQueries
    from app.db.queries.preferences import PreferencesQueries

    with Session(bind=op.get_bind()) as db:
        for user_id in db.scalars(sa.text("SELECT id FROM users ORDER BY id")):
            LibraryQueries(db).lock_user(user_id)
            PreferencesQueries(db).rescore(user_id)
        db.flush()


def downgrade():
    pass
