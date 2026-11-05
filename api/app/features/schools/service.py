from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.school import School


def list_schools(
    db: Session, curriculum: str | None = None, include_inactive: bool = False
) -> list[School]:
    query = select(School).order_by(School.name)
    if not include_inactive:
        query = query.where(School.is_active.is_(True))
    schools = db.scalars(query).all()
    # Filtered in Python so it works on both PostgreSQL arrays and SQLite JSON;
    # the school list is small.
    if curriculum is not None:
        schools = [s for s in schools if curriculum in s.curricula]
    return list(schools)


def find_school(db: Session, code: str) -> School | None:
    return db.scalar(select(School).where(School.code == code.strip().lower()))
