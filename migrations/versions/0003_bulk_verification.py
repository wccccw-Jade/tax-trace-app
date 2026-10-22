"""Retain bulk verification operation and reversal history."""
from alembic import op
import sqlalchemy as sa
revision='0003'
down_revision='0002'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('verifications',sa.Column('operation_id',sa.String(64),nullable=True))
    op.add_column('verifications',sa.Column('reversed_at',sa.String(40),nullable=True))
    op.add_column('verifications',sa.Column('reversed_by',sa.String(30),nullable=True))
    op.create_index('ix_verifications_operation_id','verifications',['operation_id'])


def downgrade():
    op.drop_index('ix_verifications_operation_id',table_name='verifications')
    for name in ['reversed_by','reversed_at','operation_id']:
        op.drop_column('verifications',name)
