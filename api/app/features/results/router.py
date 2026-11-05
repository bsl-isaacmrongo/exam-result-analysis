from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.database import get_db
from app.features.results import service
from app.features.results.analysis import analyse
from app.features.results.parsers import WorkbookError, parse_cem, parse_ib_results
from app.features.results.schemas import (
    AnalysisResponse,
    ExamSession,
    ImportResponse,
    SourceInfo,
)
from app.models.results import EXAM_SESSIONS, IMPORT_KINDS, ResultImport
from app.models.school import School
from app.models.user import User

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
PARSERS = {"cem": parse_cem, "ib_results": parse_ib_results}

imports_router = APIRouter(prefix="/api/imports", tags=["imports"])
analysis_router = APIRouter(prefix="/api/analysis", tags=["analysis"])

KindParam = Annotated[str, Form(pattern="^(" + "|".join(IMPORT_KINDS) + ")$")]
SessionParam = Annotated[str, Form(pattern="^(" + "|".join(EXAM_SESSIONS) + ")$")]


def _schools(db: Session, code: str) -> list[School]:
    schools = service.schools_for(db, code)
    if not schools and code.strip().lower() != service.ALL_SCHOOLS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="School not found")
    return schools


def _response(item: ResultImport, schools: dict[int, School], users: dict[int, User]) -> ImportResponse:
    user = users.get(item.uploaded_by_id) if item.uploaded_by_id else None
    return ImportResponse(
        id=item.id,
        school=schools[item.school_id].code,
        kind=item.kind,
        year=item.year,
        session=item.session,
        filename=item.filename,
        summary=item.summary,
        uploaded_by=(user.name or user.email) if user else None,
        created_at=_utc(item.created_at),
    )


def _utc(value: datetime) -> datetime:
    # SQLite returns naive datetimes; they are stored in UTC.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _users(db: Session, items: list[ResultImport]) -> dict[int, User]:
    ids = {i.uploaded_by_id for i in items if i.uploaded_by_id}
    return {u.id: u for u in (db.get(User, i) for i in ids) if u}


@imports_router.get("", response_model=list[ImportResponse])
def get_imports(
    school: str = Query(min_length=1, max_length=20),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ImportResponse]:
    """Imported files for a school (or every IB school for "all"), newest session first."""
    schools = _schools(db, school)
    items = service.list_imports(db, schools)
    by_id = {s.id: s for s in schools}
    users = _users(db, items)
    return [_response(i, by_id, users) for i in items]


@imports_router.post("", response_model=ImportResponse, status_code=status.HTTP_201_CREATED)
def create_import(
    file: Annotated[UploadFile, File()],
    school: Annotated[str, Form(min_length=1, max_length=20)],
    kind: KindParam,
    year: Annotated[int, Form(ge=2000, le=2100)],
    session: SessionParam,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> ImportResponse:
    """Upload a CEM baseline or IB results workbook; replaces that session's earlier import."""
    if school.strip().lower() == service.ALL_SCHOOLS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": "Choose a single school to import into.", "errors": []},
        )
    target = _schools(db, school)[0]
    if service.CURRICULUM not in target.curricula:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": f"{target.name} doesn't offer the IB.", "errors": []},
        )
    filename = file.filename or "upload.xlsx"
    if not filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": "Upload an Excel workbook (.xlsx).", "errors": []},
        )
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={"message": "The file is larger than 5 MB.", "errors": []},
        )
    try:
        parsed = PARSERS[kind](content)
    except WorkbookError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": error.message, "errors": error.errors},
        ) from error

    item = service.replace_import(db, target, kind, year, session, filename, parsed, user)
    return _response(item, {target.id: target}, {user.id: user})


@imports_router.delete(
    "/{import_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles("admin"))],
)
def delete_import(import_id: int, db: Session = Depends(get_db)) -> Response:
    item = db.get(ResultImport, import_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found")
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@analysis_router.get("/ib", response_model=AnalysisResponse)
def get_ib_analysis(
    school: str = Query(min_length=1, max_length=20),
    year: int | None = Query(default=None, ge=2000, le=2100),
    session: str | None = Query(default=None, pattern="^(" + "|".join(EXAM_SESSIONS) + ")$"),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    """IB results analysis for one exam session (default: the latest with results)."""
    schools = _schools(db, school)
    sessions = service.available_sessions(db, schools)
    if year is not None and session is not None:
        chosen: tuple[int, str] | None = (year, session)
    else:
        chosen = sessions[0] if sessions else None

    sources: dict[str, list[SourceInfo]] = {kind: [] for kind in PARSERS}
    analysis = None
    if chosen is not None:
        imports = service.session_imports(db, schools, *chosen)
        for item in imports:
            sources[item.kind].append(
                SourceInfo(filename=item.filename, created_at=_utc(item.created_at))
            )
        by_school = {s.id: s for s in schools}
        groups = []
        for school_id in sorted({i.school_id for i in imports}):
            mine = [i for i in imports if i.school_id == school_id]
            candidates = [c for i in mine if i.kind == "ib_results" for c in i.ib_candidates]
            cems = [c for i in mine if i.kind == "cem" for c in i.cem_students]
            if candidates:
                groups.append((by_school[school_id].code, candidates, cems))
        if groups:
            analysis = analyse(groups)

    return AnalysisResponse(
        school=school.strip().lower(),
        sessions=[ExamSession(year=y, session=s) for y, s in sessions],
        session=ExamSession(year=chosen[0], session=chosen[1]) if chosen else None,
        sources=sources,
        analysis=analysis,
    )
