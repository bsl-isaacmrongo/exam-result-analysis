"""Imported external results: CEM baseline predictions and final IB results.

Each import keeps the rows exactly as parsed from one workbook. CEM and IB
records are matched by student name when the analysis runs, so the two files
can be imported in either order and re-imported independently.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

IMPORT_KINDS = ("cem", "ib_results")
EXAM_SESSIONS = ("may", "nov")


class ResultImport(Base):
    __tablename__ = "result_imports"
    __table_args__ = (
        # Re-importing a file replaces the previous import of the same kind.
        UniqueConstraint(
            "school_id", "year", "session", "kind", name="uq_result_imports_session_kind"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), index=True
    )
    # "cem" (CEM IBE baseline) or "ib_results" (final IB DP/CP results).
    kind: Mapped[str] = mapped_column(String(20))
    year: Mapped[int] = mapped_column(Integer)
    # IB exam session: "may" or "nov".
    session: Mapped[str] = mapped_column(String(3))
    filename: Mapped[str] = mapped_column(String(255))
    # Counts and warnings from parsing, shown in the import history.
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    uploaded_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    cem_students: Mapped[list["CemStudent"]] = relationship(
        back_populates="result_import", cascade="all, delete-orphan"
    )
    ib_candidates: Mapped[list["IbCandidate"]] = relationship(
        back_populates="result_import", cascade="all, delete-orphan"
    )


class CemStudent(Base):
    __tablename__ = "cem_students"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_id: Mapped[int] = mapped_column(
        ForeignKey("result_imports.id", ondelete="CASCADE"), index=True
    )
    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str] = mapped_column(String(255))
    gender: Mapped[str | None] = mapped_column(String(1))
    # CEM IBE overall ability standard score (mean 100).
    baseline: Mapped[float | None] = mapped_column(Float)

    result_import: Mapped[ResultImport] = relationship(back_populates="cem_students")
    predictions: Mapped[list["CemPrediction"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


class CemPrediction(Base):
    __tablename__ = "cem_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("cem_students.id", ondelete="CASCADE"), index=True
    )
    # Subject as written in the CEM export, e.g. "IB-H-Biology".
    cem_subject: Mapped[str] = mapped_column(String(100))
    # Subject catalogue key (see features/results/subjects.py); NULL if unknown.
    subject: Mapped[str | None] = mapped_column(String(20))
    level: Mapped[str] = mapped_column(String(2))
    variant: Mapped[str | None] = mapped_column(String(10))
    # Predicted IB points; CEM predictions can be decimal and are kept unrounded.
    predicted: Mapped[float] = mapped_column(Float)

    student: Mapped[CemStudent] = relationship(back_populates="predictions")


class IbCandidate(Base):
    __tablename__ = "ib_candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_id: Mapped[int] = mapped_column(
        ForeignKey("result_imports.id", ondelete="CASCADE"), index=True
    )
    # "DP" or "CP".
    pathway: Mapped[str] = mapped_column(String(2))
    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str] = mapped_column(String(255))
    # DP core.
    ee_subject: Mapped[str | None] = mapped_column(String(50))
    ee_grade: Mapped[str | None] = mapped_column(String(1))
    tok_grade: Mapped[str | None] = mapped_column(String(1))
    core_points: Mapped[int | None] = mapped_column(Integer)
    total_points: Mapped[int | None] = mapped_column(Integer)
    # CP core and career-related study.
    rp_grade: Mapped[str | None] = mapped_column(String(1))
    btec_result: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(String(500))

    result_import: Mapped[ResultImport] = relationship(back_populates="ib_candidates")
    subjects: Mapped[list["IbSubjectResult"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )


class IbSubjectResult(Base):
    __tablename__ = "ib_subject_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("ib_candidates.id", ondelete="CASCADE"), index=True
    )
    subject: Mapped[str] = mapped_column(String(20))
    # NULL when the workbook doesn't say; the CEM level is used during analysis.
    level: Mapped[str | None] = mapped_column(String(2))
    variant: Mapped[str | None] = mapped_column(String(10))
    # 1-7, or NULL for non-graded entries such as "LD" or "Port".
    grade: Mapped[int | None] = mapped_column(Integer)
    raw: Mapped[str] = mapped_column(String(20))

    candidate: Mapped[IbCandidate] = relationship(back_populates="subjects")
