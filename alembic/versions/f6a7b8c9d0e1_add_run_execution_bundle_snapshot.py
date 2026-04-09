"""add run execution bundle snapshot columns

Frozen-at-run-time policy hash, policy body, agent version, model id, tools, and
per-run operator signature. Binds replay and claim verification to the original
execution context so operators cannot rewrite history by changing policy later.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-09 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('runs', sa.Column('proof_status', sa.String(length=16), nullable=False, server_default='unverified'))
    op.add_column('runs', sa.Column('policy_id_snapshot', sa.Integer(), nullable=True))
    op.add_column('runs', sa.Column('policy_hash_snapshot', sa.String(length=66), nullable=True))
    op.add_column('runs', sa.Column('policy_rules_snapshot', sa.JSON(), nullable=True))
    op.add_column('runs', sa.Column('agent_version_snapshot', sa.Integer(), nullable=True))
    op.add_column('runs', sa.Column('model_id_snapshot', sa.String(length=128), nullable=True))
    op.add_column('runs', sa.Column('allowed_tools_snapshot', sa.JSON(), nullable=True))
    op.add_column('runs', sa.Column('run_signature', sa.Text(), nullable=True))
    op.add_column('runs', sa.Column('run_message', sa.Text(), nullable=True))

    # Backfill existing rows: old runs without proof are marked unverified explicitly
    op.execute("UPDATE runs SET proof_status = 'verified' WHERE verified = true")


def downgrade() -> None:
    op.drop_column('runs', 'run_message')
    op.drop_column('runs', 'run_signature')
    op.drop_column('runs', 'allowed_tools_snapshot')
    op.drop_column('runs', 'model_id_snapshot')
    op.drop_column('runs', 'agent_version_snapshot')
    op.drop_column('runs', 'policy_rules_snapshot')
    op.drop_column('runs', 'policy_hash_snapshot')
    op.drop_column('runs', 'policy_id_snapshot')
    op.drop_column('runs', 'proof_status')
