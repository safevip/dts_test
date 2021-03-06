"""empty message

Revision ID: ba6f53ef3ccf
Revises: a40d49ed74db
Create Date: 2016-08-01 10:09:10.094000

"""

# revision identifiers, used by Alembic.
revision = 'ba6f53ef3ccf'
down_revision = 'a40d49ed74db'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('featureinfo',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('version_id', sa.Integer(), nullable=True),
    sa.Column('feature_name', sa.String(length=64), nullable=True),
    sa.Column('feature_descrit', sa.Text(), nullable=True),
    sa.Column('feature_status', sa.Boolean(), nullable=True),
    sa.Column('create_time', sa.DateTime(), nullable=True),
    sa.Column('update_time', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['version_id'], ['versioninfo.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('softwareinfo',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('version_id', sa.Integer(), nullable=True),
    sa.Column('software_name', sa.String(length=64), nullable=True),
    sa.Column('software_descrit', sa.Text(), nullable=True),
    sa.Column('software_status', sa.Boolean(), nullable=True),
    sa.Column('create_time', sa.DateTime(), nullable=True),
    sa.Column('update_time', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['version_id'], ['versioninfo.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.drop_column(u'versioninfo', 'software_version')
    op.drop_column(u'versioninfo', 'software_status')
    op.drop_column(u'versioninfo', 'version_features_id')
    op.drop_column(u'versioninfo', 'version_features')
    op.drop_column(u'versioninfo', 'version_features_status')
    op.drop_column(u'versioninfo', 'software_id')
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column(u'versioninfo', sa.Column('software_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True))
    op.add_column(u'versioninfo', sa.Column('version_features_status', mysql.TINYINT(display_width=1), autoincrement=False, nullable=True))
    op.add_column(u'versioninfo', sa.Column('version_features', mysql.TEXT(), nullable=True))
    op.add_column(u'versioninfo', sa.Column('version_features_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True))
    op.add_column(u'versioninfo', sa.Column('software_status', mysql.TINYINT(display_width=1), autoincrement=False, nullable=True))
    op.add_column(u'versioninfo', sa.Column('software_version', mysql.TEXT(), nullable=True))
    op.drop_table('softwareinfo')
    op.drop_table('featureinfo')
    ### end Alembic commands ###
