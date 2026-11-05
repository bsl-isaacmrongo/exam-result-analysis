from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.database import get_db
from app.features.schools.schemas import (
    CURRICULUM_SLUGS,
    SchoolCreate,
    SchoolResponse,
    SchoolUpdate,
)
from app.features.schools.service import find_school, list_schools
from app.models.school import School
from app.models.user import User

router = APIRouter(prefix="/api/schools", tags=["schools"])

_CURRICULUM_PATTERN = "^(" + "|".join(CURRICULUM_SLUGS) + ")$"


@router.get("", response_model=list[SchoolResponse])
def get_schools(
    curriculum: str | None = Query(default=None, pattern=_CURRICULUM_PATTERN),
    include_inactive: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[School]:
    """Schools offering `curriculum` (all schools when omitted), sorted by name.

    Inactive schools are only returned to admins who ask for them.
    """
    return list_schools(
        db, curriculum, include_inactive=include_inactive and user.role == "admin"
    )


@router.post(
    "",
    response_model=SchoolResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("admin"))],
)
def create_school(payload: SchoolCreate, db: Session = Depends(get_db)) -> School:
    if find_school(db, payload.code) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"School '{payload.code}' already exists",
        )
    school = School(**payload.model_dump(), is_active=True)
    db.add(school)
    db.commit()
    return school


@router.patch(
    "/{code}",
    response_model=SchoolResponse,
    dependencies=[Depends(require_roles("admin"))],
)
def update_school(
    code: str, payload: SchoolUpdate, db: Session = Depends(get_db)
) -> School:
    school = find_school(db, code)
    if school is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{field} cannot be null",
            )
        setattr(school, field, value)
    db.commit()
    return school
