from datetime import datetime

from pydantic import BaseModel


class ImportResponse(BaseModel):
    id: int
    school: str
    kind: str
    year: int
    session: str
    filename: str
    summary: dict
    uploaded_by: str | None
    created_at: datetime


class ExamSession(BaseModel):
    year: int
    session: str


class SourceInfo(BaseModel):
    filename: str
    created_at: datetime


class AnalysisResponse(BaseModel):
    school: str
    # Exam sessions with results, newest first.
    sessions: list[ExamSession]
    # The session analysed, or None when nothing has been imported yet.
    session: ExamSession | None
    # Latest import time per kind for the session (several for "all" schools).
    sources: dict[str, list[SourceInfo]]
    # See features/results/analysis.py for the shape; None without IB results.
    analysis: dict | None
