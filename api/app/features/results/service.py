from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.features.results.parsers import (
    ParsedCandidate,
    ParsedCemStudent,
    ParseResult,
)
from app.features.schools.service import list_schools
from app.models.results import (
    CemPrediction,
    CemStudent,
    IbCandidate,
    IbSubjectResult,
    ResultImport,
)
from app.models.school import School
from app.models.user import User

CURRICULUM = "ib"
ALL_SCHOOLS = "all"


def schools_for(db: Session, code: str) -> list[School]:
    """The school with `code`, or every active IB school for "all"."""
    if code.strip().lower() == ALL_SCHOOLS:
        return list_schools(db, CURRICULUM)
    school = db.scalar(select(School).where(School.code == code.strip().lower()))
    return [school] if school else []


def replace_import(
    db: Session,
    school: School,
    kind: str,
    year: int,
    session: str,
    filename: str,
    parsed: ParseResult,
    user: User,
) -> ResultImport:
    """Save a parsed workbook, replacing any earlier import of the same kind and session."""
    previous = db.scalar(
        select(ResultImport).where(
            ResultImport.school_id == school.id,
            ResultImport.kind == kind,
            ResultImport.year == year,
            ResultImport.session == session,
        )
    )
    summary = dict(parsed.summary)
    if previous is not None:
        summary["replaced"] = previous.filename
        db.delete(previous)
        db.flush()

    result_import = ResultImport(
        school_id=school.id,
        kind=kind,
        year=year,
        session=session,
        filename=filename[:255],
        summary=summary,
        uploaded_by_id=user.id,
    )
    if kind == "cem":
        result_import.cem_students = [_cem_student(r) for r in parsed.records]
    else:
        result_import.ib_candidates = [_candidate(r) for r in parsed.records]
    db.add(result_import)
    db.commit()
    db.refresh(result_import)
    return result_import


def _cem_student(record: ParsedCemStudent) -> CemStudent:
    return CemStudent(
        first_name=record.first_name,
        last_name=record.last_name,
        gender=record.gender,
        baseline=record.baseline,
        predictions=[
            CemPrediction(
                cem_subject=p.cem_subject[:100],
                subject=p.subject,
                level=p.level,
                variant=p.variant,
                predicted=p.predicted,
            )
            for p in record.predictions
        ],
    )


def _candidate(record: ParsedCandidate) -> IbCandidate:
    return IbCandidate(
        pathway=record.pathway,
        first_name=record.first_name,
        last_name=record.last_name,
        ee_subject=record.ee_subject[:50] if record.ee_subject else None,
        ee_grade=record.ee_grade,
        tok_grade=record.tok_grade,
        core_points=record.core_points,
        total_points=record.total_points,
        rp_grade=record.rp_grade,
        btec_result=record.btec_result[:50] if record.btec_result else None,
        notes=record.notes,
        subjects=[
            IbSubjectResult(
                subject=s.subject,
                level=s.level,
                variant=s.variant,
                grade=s.grade,
                raw=s.raw[:20],
            )
            for s in record.subjects
        ],
    )


def list_imports(db: Session, schools: list[School]) -> list[ResultImport]:
    if not schools:
        return []
    return list(
        db.scalars(
            select(ResultImport)
            .where(ResultImport.school_id.in_([s.id for s in schools]))
            .order_by(
                ResultImport.year.desc(),
                ResultImport.session.desc(),
                ResultImport.created_at.desc(),
            )
        )
    )


def available_sessions(db: Session, schools: list[School]) -> list[tuple[int, str]]:
    """Exam sessions with imported results, newest first."""
    if not schools:
        return []
    rows = db.execute(
        select(ResultImport.year, ResultImport.session)
        .where(
            ResultImport.school_id.in_([s.id for s in schools]),
            ResultImport.kind == "ib_results",
        )
        .distinct()
    ).all()
    return sorted(((y, s) for y, s in rows), reverse=True)


def session_imports(
    db: Session, schools: list[School], year: int, session: str
) -> list[ResultImport]:
    return list(
        db.scalars(
            select(ResultImport)
            .where(
                ResultImport.school_id.in_([s.id for s in schools]),
                ResultImport.year == year,
                ResultImport.session == session,
            )
            .options(
                selectinload(ResultImport.cem_students).selectinload(CemStudent.predictions),
                selectinload(ResultImport.ib_candidates).selectinload(IbCandidate.subjects),
            )
        )
    )
