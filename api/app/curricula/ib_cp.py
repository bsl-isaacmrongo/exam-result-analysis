from api.app.curricula.base import CurriculumAdapter
from api.app.curricula.ib_dp import IBDPAdapter


class IBCPAdapter(CurriculumAdapter):
    code = "IB_CP"

    def validate_upload(self, df):
        # CP only accepts DP course rows, must have at least 2 per student
        super().validate_upload(df)
        counts = df.groupby("student_id").size()
        if (counts < 2).any():
            raise ValueError("IB_CP requires at least 2 DP courses per student")

    def normalise_prior(self, df):
        # Same as DP: MYP/GCSE → z within subject-cohort
        return IBDPAdapter().normalise_prior(df)

    def encode_final_grade(self, df):
        return IBDPAdapter().encode_final_grade(df)
    