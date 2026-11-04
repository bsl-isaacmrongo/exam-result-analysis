import pandas as pd
from app.curricula.base import CurriculumAdapter

class IBDPAdapter(CurriculumAdapter):
    code = "IB_DP"

    def validate_upload(self, df):
        required = {"student_id","cohort","subject_code","prior_attainment","final_grade"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")

    def normalise_prior(self, df):
        df = df.copy()
        df["prior_z"] = df.groupby(["cohort","subject_code"])["prior_attainment"] \
                          .transform(lambda s: (s - s.mean()) / s.std(ddof=0))
        return df

    def encode_final_grade(self, df):
        df = df.copy()
        df["final_grade_raw"] = df["final_grade"].astype(str)
        df["final_grade"] = pd.to_numeric(df["final_grade"], errors="coerce")
        return df
