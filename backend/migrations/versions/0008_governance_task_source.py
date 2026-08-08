"""治理闭环：GovernanceTask 增加来源关联字段（告警/报告）

Revision ID: 0008
Revises: 0007
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tf_governance_task',
                  sa.Column('source_alert_id', sa.String(32),
                            nullable=False, server_default=''))
    op.add_column('tf_governance_task',
                  sa.Column('source_report_id', sa.String(32),
                            nullable=False, server_default=''))
    op.create_index('idx_gov_source_alert', 'tf_governance_task',
                    ['source_alert_id'])
    op.create_index('idx_gov_source_report', 'tf_governance_task',
                    ['source_report_id'])


def downgrade() -> None:
    op.drop_index('idx_gov_source_report', table_name='tf_governance_task')
    op.drop_index('idx_gov_source_alert', table_name='tf_governance_task')
    op.drop_column('tf_governance_task', 'source_report_id')
    op.drop_column('tf_governance_task', 'source_alert_id')
