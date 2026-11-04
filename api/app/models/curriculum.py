from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class Curriculum(Base):
    __tablename__ = "curricula"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    grade_scale: Mapped[dict] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(default=True)
