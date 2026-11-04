import pandas as pd
import statsmodels.formula.api as smf
from app.database import SessionLocal
from app.models.student_result import StudentResult
from app.models.upload import Upload
from app.curricula import get_adapter

def run_analysis(upload_id: int):
    db = SessionLocal()
    try:
        upload = db.get(Upload, upload_id)
        adapter = get_adapter(upload.curriculum_code)

        # 1. Load raw data (simplified here: in practice, re-parse CSV or store raw)
        # 2. adapter.validate_upload(df)
        # 3. df = adapter.encode_final_grade(df)
        # 4. df = adapter.normalise_prior(df)
        # 5. Write StudentResult rows
        # 6. For each subject, fit OLS: final_grade ~ prior_z
        #    Compute expected_grade and residual, write back

        upload.status = "complete"
        db.commit()
    except Exception as e:
        upload.status = "failed"
        upload.error_message = str(e)
        db.commit()
    finally:
        db.close()
