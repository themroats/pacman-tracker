"""add user_tokens table

Revision ID: a1b2c3d4e5f6
Revises: c34f504e3f4d
Create Date: 2026-03-30

Creates the user_tokens table to support multiple active tokens per user.
Migrates existing User.access_token_hash data, then drops that column.
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "c34f504e3f4d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create user_tokens table
    op.create_table(
        "user_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("client_name", sa.String(length=50), nullable=False, server_default="frontend"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_tokens_token_hash"), "user_tokens", ["token_hash"], unique=True)
    op.create_index(op.f("ix_user_tokens_user_id"), "user_tokens", ["user_id"], unique=False)

    # 2. Migrate existing token hashes from users table
    op.execute(
        """
        INSERT INTO user_tokens (user_id, token_hash, client_name, created_at)
        SELECT id, access_token_hash, 'frontend', COALESCE(updated_at, now())
        FROM users
        WHERE access_token_hash IS NOT NULL
        """
    )

    # 3. Drop the old column from users
    op.drop_index(op.f("ix_users_access_token_hash"), table_name="users")
    op.drop_column("users", "access_token_hash")


def downgrade() -> None:
    # 1. Re-add column
    op.add_column(
        "users",
        sa.Column("access_token_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(op.f("ix_users_access_token_hash"), "users", ["access_token_hash"], unique=True)

    # 2. Migrate latest token per user back
    op.execute(
        """
        UPDATE users
        SET access_token_hash = ut.token_hash
        FROM (
            SELECT DISTINCT ON (user_id) user_id, token_hash
            FROM user_tokens
            ORDER BY user_id, created_at DESC
        ) ut
        WHERE users.id = ut.user_id
        """
    )

    # 3. Drop user_tokens
    op.drop_index(op.f("ix_user_tokens_user_id"), table_name="user_tokens")
    op.drop_index(op.f("ix_user_tokens_token_hash"), table_name="user_tokens")
    op.drop_table("user_tokens")
