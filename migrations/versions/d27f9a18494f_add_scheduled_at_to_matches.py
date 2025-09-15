"""Add scheduled_at and completed_at to matches

Revision ID: d27f9a18494f
Revises: dd093dfa2ebf
Create Date: 2025-09-15 12:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = "d27f9a18494f"
down_revision = "dd093dfa2ebf"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("matches", sa.Column("scheduled_at", sa.DateTime(), nullable=True))
    op.add_column("matches", sa.Column("completed_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("matches", "completed_at")
    op.drop_column("matches", "scheduled_at")
