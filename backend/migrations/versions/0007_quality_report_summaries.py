"""Sprint8 质量巡检 Agent 扩充：QualityReport 增加向量质量与域覆盖摘要列

Revision ID: 0007
Revises: 0006
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tf_quality_report',
                  sa.Column('vector_health', sa.JSON(), nullable=True))
    op.add_column('tf_quality_report',
                  sa.Column('coverage', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('tf_quality_report', 'coverage')
    op.drop_column('tf_quality_report', 'vector_health')
