"""Sprint4 多租户隔离 + 知识库版本管理 + RBAC

Revision ID: 0003
Revises: 0002
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------- 现有表加列（SQLite 用 batch）----------------
    with op.batch_alter_table('tf_knowledge_base') as b:
        b.add_column(sa.Column('tenant_id', sa.String(32), nullable=False,
                               server_default='default'))
        b.add_column(sa.Column('visibility', sa.String(16), nullable=False,
                               server_default='tenant'))
        b.add_column(sa.Column('allowed_roles', sa.JSON(), nullable=True))
        b.add_column(sa.Column('active_version_id', sa.String(32), nullable=True))
        b.create_index('ix_kb_tenant', ['tenant_id'])

    with op.batch_alter_table('tf_document') as b:
        b.add_column(sa.Column('tenant_id', sa.String(32), nullable=False,
                               server_default='default'))
        b.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False,
                               server_default=sa.false()))
        b.create_index('ix_doc_tenant', ['tenant_id'])
        b.create_index('ix_doc_deleted', ['is_deleted'])

    with op.batch_alter_table('tf_chunk') as b:
        b.add_column(sa.Column('tenant_id', sa.String(32), nullable=False,
                               server_default='default'))
        b.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False,
                               server_default=sa.false()))
        b.create_index('ix_chunk_tenant', ['tenant_id'])
        b.create_index('ix_chunk_deleted', ['is_deleted'])

    with op.batch_alter_table('tf_conversation') as b:
        b.add_column(sa.Column('tenant_id', sa.String(32), nullable=False,
                               server_default='default'))
        b.create_index('ix_conv_tenant', ['tenant_id'])

    # ---------------- 知识库版本检查点 ----------------
    op.create_table(
        'tf_kb_version',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('kb_id', sa.String(32), nullable=False),
        sa.Column('version_no', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('label', sa.String(128), nullable=False, server_default=''),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('doc_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('doc_ids', sa.JSON(), nullable=True),
        sa.Column('chunk_ids', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.String(64), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_kb_version_kb', 'tf_kb_version', ['kb_id'])
    op.create_index('ix_kb_version_kb_no', 'tf_kb_version', ['kb_id', 'version_no'])

    # ---------------- RBAC 用户 ----------------
    op.create_table(
        'tf_user',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('username', sa.String(64), nullable=False),
        sa.Column('display_name', sa.String(64), nullable=False, server_default=''),
        sa.Column('api_key', sa.String(64), nullable=False),
        sa.Column('role', sa.String(16), nullable=False, server_default='viewer'),
        sa.Column('tenant_id', sa.String(32), nullable=False, server_default='default'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_user_api_key', 'tf_user', ['api_key'])
    op.create_index('ix_user_tenant', 'tf_user', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('ix_user_tenant', table_name='tf_user')
    op.drop_index('ix_user_api_key', table_name='tf_user')
    op.drop_table('tf_user')

    op.drop_index('ix_kb_version_kb_no', table_name='tf_kb_version')
    op.drop_index('ix_kb_version_kb', table_name='tf_kb_version')
    op.drop_table('tf_kb_version')

    with op.batch_alter_table('tf_conversation') as b:
        b.drop_index('ix_conv_tenant')
        b.drop_column('tenant_id')

    with op.batch_alter_table('tf_chunk') as b:
        b.drop_index('ix_chunk_deleted')
        b.drop_index('ix_chunk_tenant')
        b.drop_column('is_deleted')
        b.drop_column('tenant_id')

    with op.batch_alter_table('tf_document') as b:
        b.drop_index('ix_doc_deleted')
        b.drop_index('ix_doc_tenant')
        b.drop_column('is_deleted')
        b.drop_column('tenant_id')

    with op.batch_alter_table('tf_knowledge_base') as b:
        b.drop_index('ix_kb_tenant')
        b.drop_column('active_version_id')
        b.drop_column('allowed_roles')
        b.drop_column('visibility')
        b.drop_column('tenant_id')
