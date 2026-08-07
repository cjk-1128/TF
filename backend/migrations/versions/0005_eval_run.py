"""Sprint7 评测运行快照表

Revision ID: 0005
Revises: 0004
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tf_eval_run',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('tenant_id', sa.String(32), nullable=False, server_default='default'),
        sa.Column('kb_ids', sa.JSON(), nullable=True),
        sa.Column('golden_version', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('n_queries', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('n_positive', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('n_negative', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('recall_at_1', sa.Float(), nullable=True, server_default='0'),
        sa.Column('recall_at_3', sa.Float(), nullable=True, server_default='0'),
        sa.Column('recall_at_5', sa.Float(), nullable=True, server_default='0'),
        sa.Column('ndcg_at_5', sa.Float(), nullable=True, server_default='0'),
        sa.Column('mrr', sa.Float(), nullable=True, server_default='0'),
        sa.Column('hit_rate', sa.Float(), nullable=True, server_default='0'),
        sa.Column('full_hit_rate', sa.Float(), nullable=True, server_default='0'),
        sa.Column('below_floor_rate', sa.Float(), nullable=True, server_default='0'),
        sa.Column('correct_rejection_rate', sa.Float(), nullable=True, server_default='0'),
        sa.Column('candidate_recall_at_20', sa.Float(), nullable=True, server_default='0'),
        sa.Column('aggregated', sa.JSON(), nullable=True),
        sa.Column('per_query', sa.JSON(), nullable=True),
        sa.Column('baseline_delta', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(16), nullable=True, server_default='ok'),
        sa.Column('source', sa.String(16), nullable=True, server_default='api'),
        sa.Column('duration_ms', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('note', sa.String(255), nullable=True, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_tf_eval_run_tenant_id', 'tf_eval_run', ['tenant_id'])
    op.create_index('ix_tf_eval_run_status', 'tf_eval_run', ['status'])
    op.create_index('ix_tf_eval_run_created_at', 'tf_eval_run', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_tf_eval_run_created_at', table_name='tf_eval_run')
    op.drop_index('ix_tf_eval_run_status', table_name='tf_eval_run')
    op.drop_index('ix_tf_eval_run_tenant_id', table_name='tf_eval_run')
    op.drop_table('tf_eval_run')
