"""Sprint3 知识缺口持久化表

Revision ID: 0002
Revises: 0001
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tf_knowledge_gap',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('query_key', sa.String(64), nullable=False),
        sa.Column('intent', sa.String(32), nullable=False, server_default=''),
        sa.Column('domains', sa.JSON(), nullable=True),
        sa.Column('user_id', sa.String(64), nullable=False, server_default='anonymous'),
        sa.Column('occurrence_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_asked_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(16), nullable=False, server_default='open'),
        sa.Column('suggested_kb_id', sa.String(32), nullable=False, server_default=''),
        sa.Column('suggested_title', sa.String(256), nullable=False, server_default=''),
        sa.Column('linked_task_id', sa.String(32), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_tf_knowledge_gap_query_key', 'tf_knowledge_gap', ['query_key'])
    op.create_index('ix_tf_knowledge_gap_status', 'tf_knowledge_gap', ['status'])
    op.create_index('ix_tf_knowledge_gap_status_intent', 'tf_knowledge_gap',
                    ['status', 'intent'])


def downgrade() -> None:
    op.drop_index('ix_tf_knowledge_gap_status_intent', table_name='tf_knowledge_gap')
    op.drop_index('ix_tf_knowledge_gap_status', table_name='tf_knowledge_gap')
    op.drop_index('ix_tf_knowledge_gap_query_key', table_name='tf_knowledge_gap')
    op.drop_table('tf_knowledge_gap')
