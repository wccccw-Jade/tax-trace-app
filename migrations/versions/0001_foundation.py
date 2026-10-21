"""Immutable import, indexed records/edges, demo sessions, safe view audit."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('packet_imports', sa.Column('id', sa.String(64), primary_key=True), sa.Column('original', sa.Text(), nullable=False), sa.Column('report', JSONB(), nullable=False))
    op.create_table('records', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('packet_id', sa.String(64), sa.ForeignKey('packet_imports.id'), nullable=False), sa.Column('ref', sa.Text(), nullable=False), sa.Column('kind', sa.String(30), nullable=False), sa.Column('payload', JSONB(), nullable=False), sa.Column('revision', sa.Integer(), nullable=False), sa.UniqueConstraint('packet_id','ref'))
    op.create_index('ix_records_packet_id', 'records', ['packet_id'])
    op.create_index('ix_records_kind', 'records', ['kind'])
    op.create_table('evidence_edges', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('packet_id', sa.String(64), sa.ForeignKey('packet_imports.id'), nullable=False), sa.Column('source', sa.Text(), nullable=False), sa.Column('target', sa.Text(), nullable=False), sa.Column('kind', sa.String(30), nullable=False), sa.Column('resolved', sa.Boolean(), nullable=False), sa.UniqueConstraint('packet_id','source','target','kind'))
    for col in ['packet_id','source','target']:
        op.create_index('ix_evidence_edges_'+col, 'evidence_edges', [col])
    op.create_table('demo_sessions', sa.Column('token', sa.String(64), primary_key=True), sa.Column('actor_id', sa.String(30), nullable=False))
    op.create_table('audit_events', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('actor_id', sa.String(30), nullable=False), sa.Column('action', sa.String(60), nullable=False), sa.Column('subject', sa.Text(), nullable=False), sa.Column('at', sa.String(40), nullable=False))

def downgrade():
    for table in ['audit_events','demo_sessions','evidence_edges','records','packet_imports']:
        op.drop_table(table)
