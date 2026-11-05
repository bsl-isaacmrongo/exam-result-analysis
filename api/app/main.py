from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.core.middleware import CSRF_HEADER, SecurityMiddleware
from app.database import engine
from app.features.auth.router import router as auth_router
from app.features.results.router import analysis_router, imports_router
from app.features.schools.router import router as schools_router

app = FastAPI(title="Results analysis API")
app.add_middleware(SecurityMiddleware)
# Added last = outermost, so preflights and CSRF rejections get CORS headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", CSRF_HEADER],
    max_age=600,
)
app.include_router(auth_router)
app.include_router(schools_router)
app.include_router(imports_router)
app.include_router(analysis_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def database_health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
