"""add agent_memories table

Revision ID: c3f1a8d2e9b4
Revises: b7c9d2e4f0a1
Create Date: 2026-03-05 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c3f1a8d2e9b4'
down_revision: Union[str, None] = 'b7c9d2e4f0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'agent_memories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.String(length=66), nullable=True),
        sa.Column('memory_type', sa.String(length=32), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_memories_agent_id', 'agent_memories', ['agent_id'])
    op.create_index('ix_agent_memories_type', 'agent_memories', ['agent_id', 'memory_type'])


def downgrade() -> None:
    op.drop_index('ix_agent_memories_type', 'agent_memories')
    op.drop_index('ix_agent_memories_agent_id', 'agent_memories')
    op.drop_table('agent_memories')
