"""ADD lecture notes

Revision ID: c9f4c87534a5
Revises: 3890c28bd2cb
Create Date: 2021-06-27 22:56:28.498800

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c9f4c87534a5"
down_revision = "3890c28bd2cb"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "lecture_notes",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("static_file_id", sa.String(length=128), nullable=False),
        sa.Column("course_id", sa.String(length=128), nullable=False),
        sa.Column("number", sa.Integer(), nullable=True),
        sa.Column("title", sa.TEXT(), nullable=True),
        sa.Column("description", sa.TEXT(), nullable=True),
        sa.Column("hidden", sa.Boolean(), nullable=True),
        sa.Column("created", sa.DateTime(), nullable=True),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["course.id"],
        ),
        sa.ForeignKeyConstraint(
            ["static_file_id"],
            ["static_file.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_general_ci",
    )
    op.create_index(
        op.f("ix_lecture_notes_course_id"),
        "lecture_notes",
        ["course_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lecture_notes_static_file_id"),
        "lecture_notes",
        ["static_file_id"],
        unique=False,
    )
    op.drop_index("name_2", table_name="assignment")
    op.drop_index("pipeline_image_2", table_name="assignment")
    op.create_index(op.f("ix_assignment_name"), "assignment", ["name"], unique=False)
    op.create_index(
        op.f("ix_assignment_pipeline_image"),
        "assignment",
        ["pipeline_image"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_assignment_pipeline_image"), table_name="assignment")
    op.drop_index(op.f("ix_assignment_name"), table_name="assignment")
    op.create_index("pipeline_image_2", "assignment", ["pipeline_image"], unique=False)
    op.create_index("name_2", "assignment", ["name"], unique=False)
    op.drop_index(op.f("ix_lecture_notes_static_file_id"), table_name="lecture_notes")
    op.drop_index(op.f("ix_lecture_notes_course_id"), table_name="lecture_notes")
    op.drop_table("lecture_notes")
    # ### end Alembic commands ###
