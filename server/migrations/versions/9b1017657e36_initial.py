"""создание таблиц"""

import sqlalchemy as sa
from alembic import op

revision = "9b1017657e36"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "codes",
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("hash", sa.Text(), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("attempts BETWEEN 0 AND 5", name=op.f("ck_codes_attempts")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_codes")),
        sa.UniqueConstraint("email", name=op.f("uq_codes_email")),
    )
    op.create_index(op.f("ix_codes_expires_at"), "codes", ["expires_at"], unique=False)
    op.create_table(
        "genres",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_genres")),
    )
    op.create_index("uq_genres_name_lower", "genres", [sa.literal_column("lower(name)")], unique=True)
    op.create_table(
        "tags",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tags")),
    )
    op.create_index(
        "ix_tags_search",
        "tags",
        [sa.literal_column("lower(name)").label("search")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"search": "gin_trgm_ops"},
    )
    op.create_index("uq_tags_name_lower", "tags", [sa.literal_column("lower(name)")], unique=True)
    op.create_table(
        "types",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_types")),
        sa.UniqueConstraint("name", name=op.f("uq_types_name")),
    )
    op.create_table(
        "users",
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), server_default="user", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'admin')", name=op.f("ck_users_role")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "work_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_groups")),
    )
    op.create_table(
        "private_works",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("type_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column("cover", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("age_rating", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("age_rating IN ('0+','6+','12+','16+','18+')", name=op.f("ck_private_works_age_rating")),
        sa.CheckConstraint("year BETWEEN 1 AND 9999", name=op.f("ck_private_works_year")),
        sa.ForeignKeyConstraint(
            ["type_id"], ["types.id"], name=op.f("fk_private_works_type_id_types"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_private_works_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_private_works")),
        sa.UniqueConstraint("user_id", "id", name=op.f("uq_private_works_user_id")),
    )
    op.create_index(
        "ix_private_works_search",
        "private_works",
        [sa.literal_column("lower(title)").label("search")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"search": "gin_trgm_ops"},
    )
    op.create_index(op.f("ix_private_works_user_id"), "private_works", ["user_id"], unique=False)
    op.create_table(
        "user_tags",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("choice", sa.SmallInteger(), nullable=True),
        sa.Column("positive", sa.Numeric(), server_default="0", nullable=False),
        sa.Column("negative", sa.Numeric(), server_default="0", nullable=False),
        sa.Column(
            "weight",
            sa.Numeric(),
            sa.Computed(
                "(positive-negative+0.5*coalesce(choice,0))/(2+positive+negative+abs(0.5*coalesce(choice,0)))",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.CheckConstraint("choice IN (-1,1)", name=op.f("ck_user_tags_choice")),
        sa.CheckConstraint("positive>=0 AND negative>=0", name=op.f("ck_user_tags_sums")),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], name=op.f("fk_user_tags_tag_id_tags"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_tags_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "tag_id", name=op.f("pk_user_tags")),
    )
    op.create_index("ix_user_tags_tag_user", "user_tags", ["tag_id", "user_id"], unique=False)
    op.create_table(
        "works",
        sa.Column("group_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("type_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column("cover", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("age_rating", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "age_rating IN ('0+','6+','12+','16+','18+','G','PG','PG-13','R','R+','R18+')",
            name=op.f("ck_works_age_rating"),
        ),
        sa.CheckConstraint("year BETWEEN 1 AND 9999", name=op.f("ck_works_year")),
        sa.ForeignKeyConstraint(
            ["group_id"], ["work_groups.id"], name=op.f("fk_works_group_id_work_groups"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["type_id"], ["types.id"], name=op.f("fk_works_type_id_types"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_works")),
    )
    op.create_index(op.f("ix_works_group_id"), "works", ["group_id"], unique=False)
    op.create_index(
        "ix_works_search",
        "works",
        [sa.literal_column("lower(title)").label("search")],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"search": "gin_trgm_ops"},
    )
    op.create_table(
        "hidden",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_hidden_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_id"], ["works.id"], name=op.f("fk_hidden_work_id_works"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "work_id", name=op.f("pk_hidden")),
    )
    op.create_table(
        "library",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=True),
        sa.Column("private_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Text(), server_default="planned", nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=True),
        sa.Column("liked", sa.Text(), nullable=True),
        sa.Column("disliked", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("analysis", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "(liked IS NULL OR btrim(liked) <> '') AND (disliked IS NULL OR btrim(disliked) <> '') AND (comment IS NULL OR btrim(comment) <> '')",
            name=op.f("ck_library_review_nonempty"),
        ),
        sa.CheckConstraint("analysis IN ('pending','running','done','error')", name=op.f("ck_library_analysis")),
        sa.CheckConstraint("status IN ('planned','in_progress','completed','dropped')", name=op.f("ck_library_status")),
        sa.CheckConstraint(
            "(liked IS NULL AND disliked IS NULL AND comment IS NULL) = (analysis IS NULL)",
            name=op.f("ck_library_review_state"),
        ),
        sa.CheckConstraint("(work_id IS NOT NULL) <> (private_id IS NOT NULL)", name=op.f("ck_library_one_work")),
        sa.CheckConstraint(
            "coalesce(length(liked),0)+coalesce(length(disliked),0)+coalesce(length(comment),0)<=5000",
            name=op.f("ck_library_review_length"),
        ),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name=op.f("ck_library_rating")),
        sa.CheckConstraint("version >= 0", name=op.f("ck_library_version")),
        sa.ForeignKeyConstraint(
            ["user_id", "private_id"],
            ["private_works.user_id", "private_works.id"],
            name=op.f("fk_library_user_id_private_works"),
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_library_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_id"], ["works.id"], name=op.f("fk_library_work_id_works"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_library")),
        sa.UniqueConstraint("private_id", name=op.f("uq_library_private_id")),
        sa.UniqueConstraint("user_id", "work_id", name=op.f("uq_library_user_id")),
    )
    op.create_index(op.f("ix_library_analysis"), "library", ["analysis"], unique=False)
    op.create_index(op.f("ix_library_work_id"), "library", ["work_id"], unique=False)
    op.create_table(
        "private_genres",
        sa.Column("private_id", sa.Uuid(), nullable=False),
        sa.Column("genre_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["genre_id"], ["genres.id"], name=op.f("fk_private_genres_genre_id_genres"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["private_id"],
            ["private_works.id"],
            name=op.f("fk_private_genres_private_id_private_works"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("private_id", "genre_id", name=op.f("pk_private_genres")),
    )
    op.create_index("ix_private_genres_genre_private", "private_genres", ["genre_id", "private_id"], unique=False)
    op.create_table(
        "recommendations",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_recommendations_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name=op.f("fk_recommendations_work_id_works"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "work_id", name=op.f("pk_recommendations")),
    )
    op.create_index(
        "ix_recommendations_order",
        "recommendations",
        ["user_id", sa.literal_column("score DESC"), "work_id"],
        unique=False,
    )
    op.create_table(
        "work_genres",
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("genre_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["genre_id"], ["genres.id"], name=op.f("fk_work_genres_genre_id_genres"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["work_id"], ["works.id"], name=op.f("fk_work_genres_work_id_works"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("work_id", "genre_id", name=op.f("pk_work_genres")),
    )
    op.create_index("ix_work_genres_genre_work", "work_genres", ["genre_id", "work_id"], unique=False)
    op.create_table(
        "work_tags",
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], name=op.f("fk_work_tags_tag_id_tags"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_id"], ["works.id"], name=op.f("fk_work_tags_work_id_works"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("work_id", "tag_id", name=op.f("pk_work_tags")),
    )
    op.create_index("ix_work_tags_tag_work", "work_tags", ["tag_id", "work_id"], unique=False)
    op.create_table(
        "library_tags",
        sa.Column("library_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(source='review' AND value IN (-1,0,1) AND quote IS NOT NULL AND btrim(quote)<>'') OR (source='manual' AND value IN (-1,1) AND quote IS NULL) OR (source='rating' AND value IN (-0.3,-0.2,0.2,0.3) AND quote IS NULL)",
            name=op.f("ck_library_tags_signal"),
        ),
        sa.ForeignKeyConstraint(
            ["library_id"], ["library.id"], name=op.f("fk_library_tags_library_id_library"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], name=op.f("fk_library_tags_tag_id_tags"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("library_id", "tag_id", name=op.f("pk_library_tags")),
    )
    op.create_index("ix_library_tags_tag_library", "library_tags", ["tag_id", "library_id"], unique=False)


def downgrade():
    op.drop_index("ix_library_tags_tag_library", table_name="library_tags")
    op.drop_table("library_tags")
    op.drop_index("ix_work_tags_tag_work", table_name="work_tags")
    op.drop_table("work_tags")
    op.drop_index("ix_work_genres_genre_work", table_name="work_genres")
    op.drop_table("work_genres")
    op.drop_index("ix_recommendations_order", table_name="recommendations")
    op.drop_table("recommendations")
    op.drop_index("ix_private_genres_genre_private", table_name="private_genres")
    op.drop_table("private_genres")
    op.drop_index(op.f("ix_library_work_id"), table_name="library")
    op.drop_index(op.f("ix_library_analysis"), table_name="library")
    op.drop_table("library")
    op.drop_table("hidden")
    op.drop_index(
        "ix_works_search", table_name="works", postgresql_using="gin", postgresql_ops={"search": "gin_trgm_ops"}
    )
    op.drop_index(op.f("ix_works_group_id"), table_name="works")
    op.drop_table("works")
    op.drop_index("ix_user_tags_tag_user", table_name="user_tags")
    op.drop_table("user_tags")
    op.drop_index(op.f("ix_private_works_user_id"), table_name="private_works")
    op.drop_index(
        "ix_private_works_search",
        table_name="private_works",
        postgresql_using="gin",
        postgresql_ops={"search": "gin_trgm_ops"},
    )
    op.drop_table("private_works")
    op.drop_table("work_groups")
    op.drop_table("users")
    op.drop_table("types")
    op.drop_index("uq_tags_name_lower", table_name="tags")
    op.drop_index(
        "ix_tags_search", table_name="tags", postgresql_using="gin", postgresql_ops={"search": "gin_trgm_ops"}
    )
    op.drop_table("tags")
    op.drop_index("uq_genres_name_lower", table_name="genres")
    op.drop_table("genres")
    op.drop_index(op.f("ix_codes_expires_at"), table_name="codes")
    op.drop_table("codes")
