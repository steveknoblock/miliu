"""add_follows_table

Revision ID: ca34f6a3374c
Revises: ecdd16271686
Create Date: 2026-04-09

"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = 'ca34f6a3374c'
down_revision: Union[str, None] = 'ecdd16271686'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'follows',
        sa.Column('follower_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('following_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('follower_id', 'following_id'),
        sa.CheckConstraint('follower_id != following_id', name='check_no_self_follow'),
    )
    op.create_index('idx_follows_follower', 'follows', ['follower_id'])
    op.create_index('idx_follows_following', 'follows', ['following_id'])


def downgrade() -> None:
    op.drop_index('idx_follows_following', table_name='follows')
    op.drop_index('idx_follows_follower', table_name='follows')
    op.drop_table('follows')
