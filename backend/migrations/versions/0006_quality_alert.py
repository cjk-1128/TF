"""Sprint7-T2 质量巡检告警表

Revision ID: 0006
Revises: 0005
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tf_quality_alert',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('tenant_id', sa.String(32), nullable=False, server_default='default'),
        sa.Column('kb_id', sa.String(32), nullable=False, server_default=''),
        sa.Column('scope', sa.String(16), nullable=False, server_default='all'),
        sa.Column('alert_type', sa.String(24), nullable=False, server_default='low_score'),
        sa.Column('severity', sa.String(8), nullable=False, server_default='high'),
        sa.Column('score', sa.Float(), nullable=True, server_default='100.0'),
        sa.Column('threshold', sa.Float(), nullable=True, server_default='80.0'),
        sa.Column('new_high_issue_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('prev_high_issue_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('high_issue_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('issue_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('title', sa.String(255), nullable=True, server_default=''),
        sa.Column('detail', sa.String(1000), nullable=True, server_default=''),
        sa.Column('report_id', sa.String(32), nullable=True, server_default=''),
        sa.Column('resolved', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolve_note', sa.String(255), nullable=True, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_tf_quality_alert_tenant_id', 'tf_quality_alert', ['tenant_id'])
    op.create_index('ix_tf_quality_alert_resolved', 'tf_quality_alert', ['resolved'])
    op.create_index('ix_tf_quality_alert_created_at', 'tf_quality_alert', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_tf_quality_alert_created_at', table_name='tf_quality_alert')
    op.drop_index('ix_tf_quality_alert_resolved', table_name='tf_quality_alert')
    op.drop_index('ix_tf_quality_alert_tenant_id', table_name='tf_quality_alert')
    op.drop_table('tf_quality_alert')
