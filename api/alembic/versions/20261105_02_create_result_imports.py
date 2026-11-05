"""Create tables for imported CEM baselines and IB results.

Revision ID: 20261105_02
Revises: 20261105_01
Create Date: 2026-11-05
"""

from alembic import op
import sqlalchemy as sa

revision = "20261105_02"
down_revision = "20261105_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "result_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "school_id",
            sa.Integer(),
            sa.ForeignKey("schools.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("session", sa.String(length=3), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column(
            "uploaded_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("kind IN ('cem', 'ib_results')", name="ck_result_imports_kind"),
        sa.CheckConstraint("session IN ('may', 'nov')", name="ck_result_imports_session"),
        # Re-importing a file replaces the previous import of the same kind.
        sa.UniqueConstraint(
            "school_id", "year", "session", "kind", name="uq_result_imports_session_kind"
        ),
    )
    op.create_index("ix_result_imports_school_id", "result_imports", ["school_id"])

    op.create_table(
        "cem_students",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "import_id",
            sa.Integer(),
            sa.ForeignKey("result_imports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("gender", sa.String(length=1), nullable=True),
        sa.Column("baseline", sa.Float(), nullable=True),
    )
    op.create_index("ix_cem_students_import_id", "cem_students", ["import_id"])

    op.create_table(
        "cem_predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("cem_students.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cem_subject", sa.String(length=100), nullable=False),
        sa.Column("subject", sa.String(length=20), nullable=True),
        sa.Column("level", sa.String(length=2), nullable=False),
        sa.Column("variant", sa.String(length=10), nullable=True),
        sa.Column("predicted", sa.Float(), nullable=False),
    )
    op.create_index("ix_cem_predictions_student_id", "cem_predictions", ["student_id"])

    op.create_table(
        "ib_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "import_id",
            sa.Integer(),
            sa.ForeignKey("result_imports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pathway", sa.String(length=2), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("ee_subject", sa.String(length=50), nullable=True),
        sa.Column("ee_grade", sa.String(length=1), nullable=True),
        sa.Column("tok_grade", sa.String(length=1), nullable=True),
        sa.Column("core_points", sa.Integer(), nullable=True),
        sa.Column("total_points", sa.Integer(), nullable=True),
        sa.Column("rp_grade", sa.String(length=1), nullable=True),
        sa.Column("btec_result", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.CheckConstraint("pathway IN ('DP', 'CP')", name="ck_ib_candidates_pathway"),
    )
    op.create_index("ix_ib_candidates_import_id", "ib_candidates", ["import_id"])

    op.create_table(
        "ib_subject_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("ib_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(length=20), nullable=False),
        sa.Column("level", sa.String(length=2), nullable=True),
        sa.Column("variant", sa.String(length=10), nullable=True),
        sa.Column("grade", sa.Integer(), nullable=True),
        sa.Column("raw", sa.String(length=20), nullable=False),
    )
    op.create_index(
        "ix_ib_subject_results_candidate_id", "ib_subject_results", ["candidate_id"]
    )


def downgrade() -> None:
    op.drop_table("ib_subject_results")
    op.drop_table("ib_candidates")
    op.drop_table("cem_predictions")
    op.drop_table("cem_students")
    op.drop_table("result_imports")
