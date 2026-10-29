"""add user email

Revision ID: 1a2b3c4d5e6f
Revises: 03221246778b
Create Date: 2026-10-27 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '1a2b3c4d5e6f'
down_revision = '03221246778b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('email', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_column('users', 'email')