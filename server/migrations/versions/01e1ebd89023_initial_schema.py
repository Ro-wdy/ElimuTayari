"""initial schema: substrands, teachers, content units, sessions, questions, tests

Revision ID: 01e1ebd89023
Revises: 
Create Date: 2026-09-02 13:59:55.412749

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '01e1ebd89023'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('substrands',
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('learning_area', sa.String(length=64), nullable=False),
    sa.Column('strand', sa.String(length=128), nullable=False),
    sa.Column('title', sa.String(length=256), nullable=False),
    sa.PrimaryKeyConstraint('code', name=op.f('pk_substrands'))
    )
    op.create_table('content_units',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('substrand_code', sa.String(length=32), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.CheckConstraint("kind IN ('guidance', 'activity', 'materials', 'sms_pack')", name=op.f('ck_content_units_kind_valid')),
    sa.ForeignKeyConstraint(['substrand_code'], ['substrands.code'], name=op.f('fk_content_units_substrand_code_substrands'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_content_units')),
    sa.UniqueConstraint('substrand_code', 'kind', 'version', name=op.f('uq_content_units_substrand_code_kind_version'))
    )
    with op.batch_alter_table('content_units', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_content_units_substrand_code'), ['substrand_code'], unique=False)

    op.create_table('teachers',
    sa.Column('phone', sa.String(length=20), nullable=False),
    sa.Column('last_substrand', sa.String(length=32), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['last_substrand'], ['substrands.code'], name=op.f('fk_teachers_last_substrand_substrands'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('phone', name=op.f('pk_teachers'))
    )
    op.create_table('questions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('teacher_phone', sa.String(length=20), nullable=False),
    sa.Column('substrand_code', sa.String(length=32), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('source', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("source IN ('student', 'teacher')", name=op.f('ck_questions_source_valid')),
    sa.ForeignKeyConstraint(['substrand_code'], ['substrands.code'], name=op.f('fk_questions_substrand_code_substrands'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['teacher_phone'], ['teachers.phone'], name=op.f('fk_questions_teacher_phone_teachers'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_questions'))
    )
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_questions_substrand_code'), ['substrand_code'], unique=False)
        batch_op.create_index(batch_op.f('ix_questions_teacher_phone'), ['teacher_phone'], unique=False)

    op.create_table('teaching_sessions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('teacher_phone', sa.String(length=20), nullable=False),
    sa.Column('substrand_code', sa.String(length=32), nullable=False),
    sa.Column('taught_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['substrand_code'], ['substrands.code'], name=op.f('fk_teaching_sessions_substrand_code_substrands'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['teacher_phone'], ['teachers.phone'], name=op.f('fk_teaching_sessions_teacher_phone_teachers'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_teaching_sessions'))
    )
    with op.batch_alter_table('teaching_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_teaching_sessions_substrand_code'), ['substrand_code'], unique=False)
        batch_op.create_index(batch_op.f('ix_teaching_sessions_teacher_phone'), ['teacher_phone'], unique=False)

    op.create_table('tests',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('teacher_phone', sa.String(length=20), nullable=False),
    sa.Column('substrand_codes', sa.JSON(), nullable=False),
    sa.Column('items_json', sa.JSON(), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['teacher_phone'], ['teachers.phone'], name=op.f('fk_tests_teacher_phone_teachers'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tests'))
    )
    with op.batch_alter_table('tests', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tests_teacher_phone'), ['teacher_phone'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('tests', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tests_teacher_phone'))

    op.drop_table('tests')
    with op.batch_alter_table('teaching_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_teaching_sessions_teacher_phone'))
        batch_op.drop_index(batch_op.f('ix_teaching_sessions_substrand_code'))

    op.drop_table('teaching_sessions')
    with op.batch_alter_table('questions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_questions_teacher_phone'))
        batch_op.drop_index(batch_op.f('ix_questions_substrand_code'))

    op.drop_table('questions')
    op.drop_table('teachers')
    with op.batch_alter_table('content_units', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_content_units_substrand_code'))

    op.drop_table('content_units')
    op.drop_table('substrands')
