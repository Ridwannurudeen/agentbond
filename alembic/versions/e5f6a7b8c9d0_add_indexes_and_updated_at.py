"""add indexes and updated_at columns

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-08 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Indexes on frequently queried columns
    op.create_index('ix_runs_agent_id', 'runs', ['agent_id'])
    op.create_index('ix_claims_agent_id', 'claims', ['agent_id'])
    op.create_index('ix_claims_claimant_address', 'claims', ['claimant_address'])
    op.create_index('ix_claims_created_at', 'claims', ['created_at'])
    op.create_index('ix_reputation_snapshots_agent_id', 'reputation_snapshots', ['agent_id'])

    # updated_at columns
    op.add_column('agents', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.add_column('runs', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.add_column('claims', sa.Column('updated_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('claims', 'updated_at')
    op.drop_column('runs', 'updated_at')
    op.drop_column('agents', 'updated_at')

    op.drop_index('ix_reputation_snapshots_agent_id', 'reputation_snapshots')
    op.drop_index('ix_claims_created_at', 'claims')
    op.drop_index('ix_claims_claimant_address', 'claims')
    op.drop_index('ix_claims_agent_id', 'claims')
    op.drop_index('ix_runs_agent_id', 'runs')
