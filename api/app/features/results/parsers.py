"""Parse the CEM baseline and IB results workbooks (.xlsx).

Both parsers return plain dataclasses plus warnings, and raise WorkbookError
listing every invalid value (FR-1.2) so nothing partial is saved.
"""

import io
import re
import zipfile
from collections import Counter
from colorsys import rgb_to_hsv
from dataclasses import dataclass, field

from openpyxl import load_workbook
from openpyxl.cell.cell import Cell
from openpyxl.worksheet.worksheet import Worksheet

from app.features.results import subjects as catalogue

MAX_ERRORS = 50
LETTER_GRADES = frozenset("ABCDE")


class WorkbookError(ValueError):
    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.errors = (errors or [])[:MAX_ERRORS]


@dataclass
class ParsedPrediction:
    cem_subject: str
    subject: str | None
    level: str
    variant: str | None
    predicted: float


@dataclass
class ParsedCemStudent:
    first_name: str
    last_name: str
    gender: str | None
    baseline: float | None
    predictions: list[ParsedPrediction] = field(default_factory=list)


@dataclass
class ParsedSubject:
    subject: str
    level: str | None
    variant: str | None
    grade: int | None
    raw: str


@dataclass
class ParsedCandidate:
    pathway: str
    first_name: str
    last_name: str
    ee_subject: str | None = None
    ee_grade: str | None = None
    tok_grade: str | None = None
    core_points: int | None = None
    total_points: int | None = None
    rp_grade: str | None = None
    btec_result: str | None = None
    notes: str | None = None
    subjects: list[ParsedSubject] = field(default_factory=list)


@dataclass
class ParseResult:
    records: list
    summary: dict


def _open(content: bytes):
    try:
        return load_workbook(io.BytesIO(content), data_only=True)
    except (zipfile.BadZipFile, KeyError, OSError, ValueError) as error:
        raise WorkbookError("The file is not a valid Excel workbook (.xlsx).") from error


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return " ".join(str(value).split())


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = _text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def split_name(full: str) -> tuple[str, str]:
    """ "Last, First" or "First Last" → (first, last)."""
    if "," in full:
        last, first = (part.strip() for part in full.split(",", 1))
        return first, last
    parts = full.split()
    if len(parts) == 1:
        return "", parts[0]
    return " ".join(parts[:-1]), parts[-1]


# --- CEM baseline -------------------------------------------------------------

_CEM_COLUMNS = {
    "name": ("studentname", "student name", "name", "student"),
    "gender": ("gender", "sex"),
    "baseline": ("baseline", "overall", "ibe", "overall ability", "score"),
    "subject": ("subject",),
    "predicted": ("cabtic", "prediction", "predicted", "predicted points", "predicted grade"),
}


def parse_cem(content: bytes) -> ParseResult:
    sheet = _open(content).worksheets[0]
    rows = sheet.iter_rows(values_only=True)
    header = [_text(v).lower() for v in next(rows, ())]
    columns: dict[str, int] = {}
    for key, names in _CEM_COLUMNS.items():
        index = next((i for i, h in enumerate(header) if h in names), None)
        if index is not None:
            columns[key] = index
    missing = [k for k in ("name", "subject", "predicted") if k not in columns]
    if missing:
        raise WorkbookError(
            "This doesn't look like a CEM baseline export.",
            [f"Missing column: {', '.join(missing)} (expected headers like "
             "StudentName, Gender, baseline, Subject, CABTIC)."],
        )

    errors: list[str] = []
    unknown_subjects: Counter[str] = Counter()
    students: dict[str, ParsedCemStudent] = {}
    seen: set[tuple[str, str]] = set()

    def cell(row: tuple, key: str) -> object:
        index = columns.get(key)
        return row[index] if index is not None and index < len(row) else None

    for line, row in enumerate(rows, start=2):
        name = _text(cell(row, "name"))
        subject_text = _text(cell(row, "subject"))
        predicted_value = cell(row, "predicted")
        if not name and not subject_text:
            continue
        if not name:
            errors.append(f"Row {line}: student name is missing.")
            continue
        try:
            key, level, variant = catalogue.cem_subject(subject_text)
        except ValueError as error:
            errors.append(f"Row {line}: {error}.")
            continue
        predicted = _number(predicted_value)
        if predicted is None or not 0 < predicted <= 7:
            errors.append(
                f"Row {line}: predicted points '{_text(predicted_value)}' for {name} "
                "must be a number between 1 and 7."
            )
            continue
        baseline_value = cell(row, "baseline")
        baseline = _number(baseline_value)
        if _text(baseline_value) and (baseline is None or not 0 < baseline < 300):
            errors.append(f"Row {line}: baseline '{_text(baseline_value)}' is not a valid score.")
            continue
        gender = _text(cell(row, "gender")).upper()[:1] or None
        if gender not in (None, "M", "F"):
            gender = None

        student = students.get(name.lower())
        if student is None:
            first, last = split_name(name)
            student = students[name.lower()] = ParsedCemStudent(first, last, gender, baseline)
        if (name.lower(), subject_text.lower()) in seen:
            errors.append(f"Row {line}: {name} has {subject_text} more than once.")
            continue
        seen.add((name.lower(), subject_text.lower()))
        if key is None:
            unknown_subjects[subject_text] += 1
        student.predictions.append(
            ParsedPrediction(subject_text, key, level, variant, predicted)
        )

    if errors:
        raise WorkbookError(f"{len(errors)} row(s) in the CEM file need fixing.", errors)
    if not students:
        raise WorkbookError("The CEM file has no student rows.")

    warnings = [
        f"No IB subject matches CEM subject '{s}' ({n} prediction(s) kept but not used for VA)."
        for s, n in sorted(unknown_subjects.items())
    ]
    records = list(students.values())
    return ParseResult(
        records,
        {
            "students": len(records),
            "predictions": sum(len(s.predictions) for s in records),
            "warnings": warnings,
        },
    )


# --- IB results ---------------------------------------------------------------


def _fill_colour(cell: Cell) -> str | None:
    """Colour category of a cell fill: "green", "yellow", "other" or None (no fill)."""
    fill = cell.fill
    if fill is None or fill.fill_type in (None, "none"):
        return None
    colour = fill.fgColor
    if colour is None or colour.type != "rgb" or not isinstance(colour.rgb, str):
        # Theme and indexed colours are the default white/automatic fills here.
        return None
    rgb = colour.rgb[-6:]
    try:
        r, g, b = (int(rgb[i : i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None
    hue, saturation, value = rgb_to_hsv(r, g, b)
    if saturation < 0.15 or value < 0.2:
        return None
    degrees = hue * 360
    if 45 <= degrees < 72:
        return "yellow"
    if 72 <= degrees < 170:
        return "green"
    return "other"


def _level_from_fill(key: str, colour: str | None) -> tuple[str | None, str | None]:
    """The workbook's colour legend: no fill = HL, green = SL, yellow = ab initio / Maths AI."""
    subject = catalogue.BY_KEY[key]
    if colour is None:
        return "HL", "aa" if subject.is_maths else None
    if colour == "green":
        return "SL", "aa" if subject.is_maths else None
    if colour == "yellow":
        if subject.has_ab_initio:
            return "SL", "ab"
        if subject.is_maths:
            return "SL", "ai"
    return None, None


def _find_header(sheet: Worksheet) -> int | None:
    best, best_row = 0, None
    for row in sheet.iter_rows(min_row=1, max_row=min(sheet.max_row, 15)):
        hits = sum(1 for c in row if catalogue.result_heading(c.value))
        if hits > best:
            best, best_row = hits, row[0].row
    return best_row if best >= 2 else None


def _pathway(sheet: Worksheet, labels: dict[int, str]) -> str:
    title = sheet.title.upper()
    if "CP" in title:
        return "CP"
    if "DP" in title:
        return "DP"
    return "CP" if {"btec", "rp"} & set(labels.values()) else "DP"


def parse_ib_results(content: bytes) -> ParseResult:
    workbook = _open(content)
    errors: list[str] = []
    warnings: list[str] = []
    candidates: list[ParsedCandidate] = []
    non_graded: Counter[str] = Counter()

    for sheet in workbook.worksheets:
        header_row = _find_header(sheet)
        if header_row is None:
            continue

        labels: dict[int, str] = {}
        subject_columns: dict[int, tuple[str, str | None, str | None]] = {}
        for column in range(1, sheet.max_column + 1):
            heading = sheet.cell(header_row, column).value
            parsed = catalogue.result_heading(heading)
            if parsed:
                subject_columns[column] = parsed
                continue
            text = _text(heading).lower()
            if not text and header_row > 1:
                text = _text(sheet.cell(header_row - 1, column).value).lower()
            if text and not text.replace(".", "").isdigit():
                labels[column] = text
        pathway = _pathway(sheet, labels)
        column_of = {name: col for col, name in sorted(labels.items(), reverse=True)}

        def find(*names: str) -> int | None:
            return next((column_of[n] for n in names if n in column_of), None)

        ee_col, tok_col = find("ee"), find("tok")
        ep_col = find("ep", "core points", "core", "bonus")
        total_col = find("total", "total points")
        notes_col = find("notes", "note", "comments")
        btec_col = next((c for c, n in labels.items() if n.startswith("btec") or n == "crs"), None)
        rp_col = find("rp")
        first_subject = min(subject_columns)

        for row in range(header_row + 1, sheet.max_row + 1):
            index_value = sheet.cell(row, 1).value
            name_cells = [
                _text(sheet.cell(row, c).value) for c in range(2, first_subject)
            ]
            names = [n for n in name_cells if n]
            if _number(index_value) is None or not names:
                continue
            if len(name_cells) >= 2 and name_cells[0] and name_cells[1]:
                first, last = name_cells[0], name_cells[1]
            else:
                first, last = split_name(" ".join(names))
            who = f"{sheet.title} row {row} ({first} {last})"
            candidate = ParsedCandidate(pathway=pathway, first_name=first, last_name=last)

            for column, (key, level, variant) in subject_columns.items():
                cell = sheet.cell(row, column)
                raw = _text(cell.value)
                if not raw:
                    continue
                grade = _number(cell.value)
                if grade is None:
                    non_graded[raw] += 1
                    candidate.subjects.append(ParsedSubject(key, level, variant, None, raw))
                    continue
                if not grade.is_integer() or not 1 <= grade <= 7:
                    errors.append(f"{who}: {catalogue.label(key, level, variant)} grade "
                                  f"'{raw}' must be a whole number from 1 to 7.")
                    continue
                if level is None:
                    level, fill_variant = _level_from_fill(key, _fill_colour(cell))
                    variant = variant or fill_variant
                    if level is None:
                        warnings.append(
                            f"{who}: couldn't tell the level of {catalogue.BY_KEY[key].short} "
                            "from the cell colour; the CEM level is used if available."
                        )
                candidate.subjects.append(ParsedSubject(key, level, variant, int(grade), raw))

            def letter(column: int | None, what: str) -> str | None:
                if column is None:
                    return None
                raw = _text(sheet.cell(row, column).value).upper()
                if not raw:
                    return None
                if raw not in LETTER_GRADES:
                    errors.append(f"{who}: {what} grade '{raw}' must be a letter A–E.")
                    return None
                return raw

            def whole(column: int | None, what: str, low: int, high: int) -> int | None:
                if column is None:
                    return None
                raw = _text(sheet.cell(row, column).value)
                if not raw:
                    return None
                value = _number(raw)
                if value is None or not value.is_integer() or not low <= value <= high:
                    errors.append(f"{who}: {what} '{raw}' must be a whole number from {low} to {high}.")
                    return None
                return int(value)

            if ee_col is not None:
                ee_first = _text(sheet.cell(row, ee_col).value)
                ee_next = _text(sheet.cell(row, ee_col + 1).value)
                next_is_grade = ee_col + 1 not in labels and ee_col + 1 not in subject_columns
                if next_is_grade and ee_next:
                    candidate.ee_subject = ee_first or None
                    candidate.ee_grade = letter(ee_col + 1, "EE")
                else:
                    candidate.ee_grade = letter(ee_col, "EE")
            candidate.tok_grade = letter(tok_col, "TOK")
            candidate.rp_grade = letter(rp_col, "Reflective Project")
            candidate.core_points = whole(ep_col, "Core points", 0, 3)
            candidate.total_points = whole(total_col, "Total points", 0, 45)
            if btec_col is not None:
                candidate.btec_result = _text(sheet.cell(row, btec_col).value) or None
            if notes_col is not None:
                candidate.notes = _text(sheet.cell(row, notes_col).value)[:500] or None
            candidates.append(candidate)

    if errors:
        raise WorkbookError(f"{len(errors)} value(s) in the results file need fixing.", errors)
    if not candidates:
        raise WorkbookError(
            "No IB results found.",
            ["Expected a sheet (e.g. IBDP or IBCP) with subject columns such as Eng, Bio, Mat "
             "and one numbered row per student."],
        )

    duplicates = Counter(
        (c.pathway, c.first_name.lower(), c.last_name.lower()) for c in candidates
    )
    for (pathway, first, last), count in duplicates.items():
        if count > 1:
            warnings.append(f"{first} {last} appears {count} times in the {pathway} results.")
    if non_graded:
        values = ", ".join(f"'{v}' ×{n}" for v, n in sorted(non_graded.items()))
        warnings.append(f"Non-numeric subject entries kept without a grade: {values}.")

    by_pathway = Counter(c.pathway for c in candidates)
    return ParseResult(
        candidates,
        {
            "dp_candidates": by_pathway["DP"],
            "cp_candidates": by_pathway["CP"],
            "subject_results": sum(
                1 for c in candidates for s in c.subjects if s.grade is not None
            ),
            "warnings": warnings,
        },
    )
