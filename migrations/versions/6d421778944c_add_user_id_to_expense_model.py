"""Add user_id to Expense model

Revision ID: 6d421778944c
Revises:
Create Date: 2025-09-08 19:09:05.414472

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6d421778944c'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_expenses_user_id_users', 'users', ['user_id'], ['id'])


def downgrade():
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.drop_constraint('fk_expenses_user_id_users', type_='foreignkey')
        batch_op.drop_column('user_id')
