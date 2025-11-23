"""Create users table

Revision ID: 6b67da18a101
Revises: 
Create Date: 2025-11-23 11:56:17.516785

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b67da18a101'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False, comment='User email address (unique identifier)'),
        sa.Column('hashed_password', sa.String(length=255), nullable=False, comment='Bcrypt hashed password'),
        sa.Column('full_name', sa.String(length=255), nullable=False, comment='User full name'),
        sa.Column('role', sa.String(length=20), nullable=False, comment='User role (USER/VIP/ADMIN)'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true'), comment='Whether user account is active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Record creation timestamp'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Record last update timestamp'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )

    # Create indexes
    op.create_index('ix_users_email', 'users', ['email'], unique=False)
    op.create_index('ix_users_role', 'users', ['role'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_users_role', table_name='users')
    op.drop_index('ix_users_email', table_name='users')

    # Drop table
    op.drop_table('users')
