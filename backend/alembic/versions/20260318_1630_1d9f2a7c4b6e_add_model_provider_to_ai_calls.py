"""add model_provider to ai_calls

Revision ID: 1d9f2a7c4b6e
Revises: c7a1f3e9d2b4
Create Date: 2026-03-18 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1d9f2a7c4b6e"
down_revision: Union[str, None] = "c7a1f3e9d2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_calls",
        sa.Column(
            "model_provider",
            sa.String(length=50),
            nullable=True,
        ),
    )
    op.create_index(op.f("ix_ai_calls_model_provider"), "ai_calls", ["model_provider"], unique=False)

    op.execute(
        """
        UPDATE ai_calls
        SET model_provider = CASE
            WHEN metadata IS NOT NULL AND metadata->>'provider' IS NOT NULL AND metadata->>'provider' <> ''
                THEN metadata->>'provider'
            WHEN model ILIKE 'MiniMax-%'
                THEN 'minimax'
            ELSE 'openai'
        END
        WHERE model_provider IS NULL OR model_provider = ''
        """
    )
    op.alter_column("ai_calls", "model_provider", nullable=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_calls_model_provider"), table_name="ai_calls")
    op.drop_column("ai_calls", "model_provider")
