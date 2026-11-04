from sqlalchemy import String, Integer, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
from app.models.base import TimestampMixin

class StudentResult(Base, TimestampMixin):
    __tablename__ = "student_results"
    __table_args__ = (
        UniqueConstraint("student_id", "cohort", "curriculum_code", "subject_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id"))
    student_id: Mapped[str] = mapped_column(String(50), index=True)
    curriculum_code: Mapped[str] = mapped_column(String(20), ForeignKey("curricula.code"))
    cohort: Mapped[int] = mapped_column(Integer, index=True)
    subject_code: Mapped[str] = mapped_column(String(50), index=True)
    prior_attainment: Mapped[float | None] = mapped_column(Numeric(6, 2))
    prior_z: Mapped[float | None] = mapped_column(Numeric(8, 4))
    final_grade: Mapped[float | None] = mapped_column(Numeric(4, 1))
    final_grade_raw: Mapped[str | None] = mapped_column(String(10))
    expected_grade: Mapped[float | None] = mapped_column(Numeric(4, 1))
    residual: Mapped[float | None] = mapped_column(Numeric(6, 2))
