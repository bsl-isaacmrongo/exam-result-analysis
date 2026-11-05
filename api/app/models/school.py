from sqlalchemy import JSON, Boolean, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

# Native text[] on PostgreSQL; JSON elsewhere (the SQLite test database).
CurriculaList = JSON().with_variant(ARRAY(String(20)), "postgresql")


class School(Base, TimestampMixin):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Short lowercase slug, used in dashboard URLs: /ib/<code>/overview.
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    # Curriculum slugs offered by the school, e.g. ["ib", "igcse"].
    curricula: Mapped[list[str]] = mapped_column(CurriculaList, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
