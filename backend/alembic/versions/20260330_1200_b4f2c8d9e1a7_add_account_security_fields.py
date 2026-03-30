"""add account security fields

Revision ID: b4f2c8d9e1a7
Revises: 5b7c3d1e8f2a
Create Date: 2026-03-30 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b4f2c8d9e1a7"
down_revision: Union[str, None] = "5b7c3d1e8f2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    op.create_table(
        "user_security_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("token_type", sa.String(length=50), nullable=False),
        sa.Column("target_email", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_user_security_tokens_user_id",
        "user_security_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "idx_user_security_tokens_user_type",
        "user_security_tokens",
        ["user_id", "token_type"],
        unique=False,
    )
    op.create_index(
        "idx_user_security_tokens_expires_at",
        "user_security_tokens",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_user_security_tokens_expires_at", table_name="user_security_tokens")
    op.drop_index("idx_user_security_tokens_user_type", table_name="user_security_tokens")
    op.drop_index("ix_user_security_tokens_user_id", table_name="user_security_tokens")
    op.drop_table("user_security_tokens")

    op.drop_column("users", "preferences")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "email_verified_at")
