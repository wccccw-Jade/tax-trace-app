"""Persist each staff member's acknowledged workpaper activity cursor."""
from alembic import op
import sqlalchemy as sa
revision='0004'
down_revision='0003'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('last_seen',
        sa.Column('packet_id',sa.String(64),sa.ForeignKey('packet_imports.id'),primary_key=True),
        sa.Column('actor_id',sa.String(30),primary_key=True),
        sa.Column('cursor',sa.Integer(),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('at',sa.String(40),nullable=False))


def downgrade():
    op.drop_table('last_seen')
