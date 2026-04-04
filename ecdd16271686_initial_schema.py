"""initial_schema

Revision ID: ecdd16271686
Revises: 
Create Date: 2026-04-02

"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = 'ecdd16271686'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Users ──────────────────────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('username', sa.String(50), nullable=False, unique=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('idx_users_username', 'users', ['username'])
    op.create_index('idx_users_email', 'users', ['email'])

    # ── Nodes ──────────────────────────────────────────────────────────────────
    op.create_table(
        'nodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('node_type', sa.String(20), nullable=False, server_default='user_post'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.CheckConstraint("node_type IN ('user_post', 'web_content')", name='check_node_type'),
    )
    op.create_index('idx_nodes_created_by', 'nodes', ['created_by'])
    op.create_index('idx_nodes_created_at', 'nodes', [sa.text('created_at DESC')])
    op.create_index('idx_nodes_metadata', 'nodes', ['metadata'], postgresql_using='gin')

    # ── Graphs ─────────────────────────────────────────────────────────────────
    op.create_table(
        'graphs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('key_node_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('nodes.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('parent_graph_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('graphs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('shift_type', sa.String(20), nullable=True),
        sa.CheckConstraint("shift_type IS NULL OR shift_type IN ('with_context', 'fresh')", name='check_shift_type'),
    )
    op.create_index('idx_graphs_created_by', 'graphs', ['created_by'])
    op.create_index('idx_graphs_key_node', 'graphs', ['key_node_id'])
    op.create_index('idx_graphs_parent', 'graphs', ['parent_graph_id'])
    op.create_index('idx_graphs_created_at', 'graphs', [sa.text('created_at DESC')])

    # ── Edges ──────────────────────────────────────────────────────────────────
    op.create_table(
        'edges',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('graph_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('graphs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_node_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_node_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relationship_type', sa.String(20), nullable=False, server_default='context_for'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint("relationship_type = 'context_for'", name='check_relationship_type'),
        sa.CheckConstraint('source_node_id != target_node_id', name='check_different_nodes'),
        sa.UniqueConstraint('graph_id', 'source_node_id', 'target_node_id', name='unique_edge_per_graph'),
    )
    op.create_index('idx_edges_graph', 'edges', ['graph_id'])
    op.create_index('idx_edges_source', 'edges', ['source_node_id'])
    op.create_index('idx_edges_target', 'edges', ['target_node_id'])

    # ── Shares ─────────────────────────────────────────────────────────────────
    op.create_table(
        'shares',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('graph_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('graphs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('shared_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('shared_with', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('share_type', sa.String(20), nullable=False),
        sa.Column('share_token', sa.String(64), unique=True, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("share_type IN ('private', 'link', 'public')", name='check_share_type'),
        sa.UniqueConstraint('graph_id', 'shared_by', 'shared_with', name='unique_private_share'),
    )
    op.create_index('idx_shares_graph', 'shares', ['graph_id'])
    op.create_index('idx_shares_shared_with', 'shares', ['shared_with'])
    op.create_index('idx_shares_share_token', 'shares', ['share_token'])
    op.create_index('idx_shares_created_at', 'shares', [sa.text('created_at DESC')])

    # ── updated_at trigger ─────────────────────────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    for table in ('users', 'nodes', 'graphs'):
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)


def downgrade() -> None:
    for table in ('users', 'nodes', 'graphs'):
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")

    op.drop_table('shares')
    op.drop_table('edges')
    op.drop_table('graphs')
    op.drop_table('nodes')
    op.drop_table('users')
