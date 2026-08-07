"""Sprint6 知识库质量巡检报告表

Revision ID: 0004
Revises: 0003
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tf_quality_report',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('kb_id', sa.String(32), nullable=True, server_default=''),
        sa.Column('tenant_id', sa.String(32), nullable=False, server_default='default'),
        sa.Column('scope', sa.String(16), nullable=True, server_default='all'),
        sa.Column('score', sa.Float(), nullable=True, server_default='100.0'),
        sa.Column('total_docs', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_chunks', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('issue_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('issue_counts', sa.JSON(), nullable=True),
        sa.Column('issues', sa.JSON(), nullable=True),
        sa.Column('suggestions', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_tf_quality_report_kb_id', 'tf_quality_report', ['kb_id'])
    op.create_index('ix_tf_quality_report_tenant_id', 'tf_quality_report', ['tenant_id'])
    op.create_index('ix_tf_quality_report_created_at', 'tf_quality_report', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_tf_quality_report_created_at', table_name='tf_quality_report')
    op.drop_index('ix_tf_quality_report_tenant_id', table_name='tf_quality_report')
    op.drop_index('ix_tf_quality_report_kb_id', table_name='tf_quality_report')
    op.drop_table('tf_quality_report')
