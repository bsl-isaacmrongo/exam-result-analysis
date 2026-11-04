from fastapi import APIRouter, UploadFile, Form, Depends, BackgroundTasks
from sqlalchemy.orm import Session
import pandas as pd, io
from app.database import get_db
from app.models.upload import Upload
from app.features.analysis.tasks import run_analysis

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

@router.post("")
async def upload_csv(
    file: UploadFile,
    curriculum_code: str = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))
    upload = Upload(filename=file.filename, curriculum_code=curriculum_code,
                    status="pending", row_count=len(df))
    db.add(upload); db.commit(); db.refresh(upload)

    background_tasks.add_task(run_analysis, upload.id)
    return {"upload_id": upload.id, "status": "pending"}
