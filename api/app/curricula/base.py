from abc import ABC, abstractmethod
import pandas as pd

class CurriculumAdapter(ABC):
    code: str

    @abstractmethod
    def validate_upload(self, df: pd.DataFrame) -> None:
        """Raise ValueError if required columns missing or invalid."""

    @abstractmethod
    def normalise_prior(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add prior_z column, computed within (cohort, subject_code)."""

    @abstractmethod
    def encode_final_grade(self, df: pd.DataFrame) -> pd.DataFrame:
        """Map raw grade to numeric, keep raw in final_grade_raw."""
