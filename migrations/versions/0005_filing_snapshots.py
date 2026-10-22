"""Immutable filing snapshots; submission and branch activity remains versioned separately."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='0005'
down_revision='0004'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('filing_snapshots',
        sa.Column('id',sa.String(64),primary_key=True),
        sa.Column('packet_id',sa.String(64),sa.ForeignKey('packet_imports.id'),nullable=False),
        sa.Column('branch_ref',sa.Text(),nullable=False),
        sa.Column('parent_id',sa.String(64),sa.ForeignKey('filing_snapshots.id'),nullable=True),
        sa.Column('content',JSONB(),nullable=False),sa.Column('digest',sa.String(64),nullable=False),
        sa.Column('actor_id',sa.String(30),nullable=False),sa.Column('at',sa.String(40),nullable=False))
    op.create_index('ix_filing_snapshots_packet_id','filing_snapshots',['packet_id'])
    op.execute("CREATE FUNCTION prevent_filing_snapshot_change() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Filing snapshots are immutable'; END; $$")
    op.execute('CREATE TRIGGER immutable_filing_snapshot BEFORE UPDATE OR DELETE ON filing_snapshots FOR EACH ROW EXECUTE FUNCTION prevent_filing_snapshot_change()')


def downgrade():
    op.drop_table('filing_snapshots')
    op.execute('DROP FUNCTION prevent_filing_snapshot_change()')
