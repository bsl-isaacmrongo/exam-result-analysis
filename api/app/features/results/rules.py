"""IB awarding rules (SRS sections 3.2–3.5), kept as data where possible."""

from dataclasses import dataclass

# Core points from EE (rows) and TOK (columns); None = failing condition.
CORE_MATRIX: dict[str, dict[str, int | None]] = {
    "A": {"A": 3, "B": 3, "C": 2, "D": 2, "E": None},
    "B": {"A": 3, "B": 2, "C": 2, "D": 1, "E": None},
    "C": {"A": 2, "B": 2, "C": 1, "D": 0, "E": None},
    "D": {"A": 2, "B": 1, "C": 0, "D": 0, "E": None},
    "E": {"A": None, "B": None, "C": None, "D": None, "E": None},
}

DIPLOMA_MIN_POINTS = 24
HL_MIN_POINTS = 12
SL_MIN_POINTS = 9
SL_MIN_POINTS_TWO_SUBJECTS = 6
DP_SUBJECT_COUNT = 6

# |VA| at or above this is "significant" (SRS 3.5).
VA_THRESHOLD = 1.0


@dataclass(frozen=True)
class Condition:
    code: str
    message: str


def core_points(ee: str | None, tok: str | None) -> int | None:
    if not ee or not tok:
        return None
    return CORE_MATRIX[ee][tok]


def diploma_conditions(
    grades: list[tuple[str | None, int]], ee: str | None, tok: str | None, total: int | None
) -> list[Condition]:
    """Failing conditions D1–D7 for a DP candidate; `grades` holds (level, grade).

    D8 (CAS) is not in the imported results, so it is not evaluated.
    """
    failing: list[Condition] = []
    if len(grades) < DP_SUBJECT_COUNT:
        failing.append(
            Condition("D0", f"Only {len(grades)} of {DP_SUBJECT_COUNT} subject grades recorded")
        )
    if total is not None and total < DIPLOMA_MIN_POINTS:
        failing.append(Condition("D1", f"Total {total} is below {DIPLOMA_MIN_POINTS}"))

    hl = sorted((g for level, g in grades if level == "HL"), reverse=True)[:3]
    if hl and sum(hl) < HL_MIN_POINTS:
        failing.append(Condition("D2", f"HL points {sum(hl)} are below {HL_MIN_POINTS}"))
    sl = [g for level, g in grades if level == "SL"]
    sl_min = SL_MIN_POINTS_TWO_SUBJECTS if len(sl) == 2 else SL_MIN_POINTS
    if sl and sum(sl) < sl_min:
        failing.append(Condition("D3", f"SL points {sum(sl)} are below {sl_min}"))

    values = [g for _, g in grades]
    if 1 in values:
        failing.append(Condition("D4", "A grade 1 was awarded"))
    if values.count(2) >= 3:
        failing.append(Condition("D5", f"{values.count(2)} grade 2s"))
    low = sum(1 for g in values if g <= 3)
    if low >= 4:
        failing.append(Condition("D6", f"{low} grades of 3 or lower"))
    if "E" in (ee, tok):
        failing.append(Condition("D7", "Grade E in TOK or EE"))
    return failing


def _btec_failed(result: str) -> bool:
    text = result.upper()
    return "FAIL" in text or "U" in text.split()


def certificate_conditions(
    grades: list[int], rp_grade: str | None, btec_result: str | None
) -> tuple[list[Condition], list[str]]:
    """Failing CP conditions, plus those that couldn't be checked (data not imported)."""
    failing: list[Condition] = []
    unchecked: list[str] = []
    passed = sum(1 for g in grades if g >= 3)
    if passed < 2:
        failing.append(Condition("C1", f"Only {passed} DP course(s) at grade 3 or higher"))
    if 1 in grades:
        failing.append(Condition("C1", "A grade 1 was awarded in a DP course"))
    if rp_grade is None:
        unchecked.append("Reflective Project")
    elif rp_grade == "E":
        failing.append(Condition("C2", "Reflective Project grade E"))
    if btec_result is None:
        unchecked.append("Career-related study")
    elif _btec_failed(btec_result):
        failing.append(Condition("C6", f"Career-related study not passed ({btec_result})"))
    unchecked += ["Personal and Professional Skills", "Service Learning", "Language Development"]
    return failing, unchecked
