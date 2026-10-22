"""Evidence-bound verification, original-preserving adjustments and independent review."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('verifications',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('record_id',sa.Integer(),sa.ForeignKey('records.id'),nullable=False),sa.Column('actor_id',sa.String(30),nullable=False),sa.Column('method',sa.String(60),nullable=False),sa.Column('note',sa.Text(),nullable=False),sa.Column('evidence',JSONB(),nullable=False),sa.Column('value',sa.Text(),nullable=False),sa.Column('subject_revision',sa.Integer(),nullable=False),sa.Column('fingerprint',sa.String(64),nullable=False),sa.Column('at',sa.String(40),nullable=False))
    op.create_index('ix_verifications_record_id','verifications',['record_id'])
    op.create_table('adjustments',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('record_id',sa.Integer(),sa.ForeignKey('records.id'),nullable=False),sa.Column('actor_id',sa.String(30),nullable=False),sa.Column('original_value',sa.Text(),nullable=False),sa.Column('proposed_value',sa.Text(),nullable=False),sa.Column('category',sa.String(40),nullable=False),sa.Column('reason',sa.Text(),nullable=False),sa.Column('evidence',JSONB(),nullable=False),sa.Column('effect',JSONB(),nullable=False),sa.Column('status',sa.String(30),nullable=False),sa.Column('at',sa.String(40),nullable=False))
    op.create_index('ix_adjustments_record_id','adjustments',['record_id'])
    op.create_table('adjustment_reviews',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('adjustment_id',sa.Integer(),sa.ForeignKey('adjustments.id'),nullable=False),sa.Column('actor_id',sa.String(30),nullable=False),sa.Column('decision',sa.String(20),nullable=False),sa.Column('note',sa.Text(),nullable=False),sa.Column('evidence',JSONB(),nullable=False),sa.Column('fingerprint',sa.String(64),nullable=False),sa.Column('at',sa.String(40),nullable=False))
    op.create_index('ix_adjustment_reviews_adjustment_id','adjustment_reviews',['adjustment_id'])

def downgrade():
    for name in ['adjustment_reviews','adjustments','verifications']:
        op.drop_table(name)
