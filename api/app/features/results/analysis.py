"""Results analysis: award status, value added and cohort statistics.

Works on any objects with the attribute names of the ORM models in
app/models/results.py (the parser dataclasses have the same shape).
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from statistics import fmean
from typing import Any

from app.features.results import rules
from app.features.results import subjects as catalogue
from app.features.results.matching import match_students

PATHWAYS = ("dp", "cp", "combined")
GRADES = range(1, 8)
# CEM IBE standard-score bands for the residual matrix (FR-3.4).
BASELINE_BANDS: tuple[tuple[str, float, float], ...] = (
    ("Below 90", float("-inf"), 90),
    ("90–99", 90, 100),
    ("100–109", 100, 110),
    ("110–119", 110, 120),
    ("120+", 120, float("inf")),
)


def _mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return round(fmean(values), 2) if values else None


def _pct(part: int, whole: int) -> float | None:
    return round(part / whole * 100, 1) if whole else None


def _name(person: Any) -> str:
    return " ".join(f"{person.first_name} {person.last_name}".split())


def _in(student: dict, pathway: str) -> bool:
    return pathway == "combined" or student["pathway"] == pathway.upper()


def _subject_entries(candidate: Any, cem: Any | None) -> tuple[list[dict], list[str]]:
    entries: list[dict] = []
    other: list[str] = []
    predictions = list(cem.predictions) if cem else []
    for result in candidate.subjects:
        if result.grade is None:
            other.append(f"{catalogue.BY_KEY[result.subject].short}: {result.raw}")
            continue
        matching = [
            p
            for p in predictions
            if catalogue.prediction_matches(result.subject, result.variant, p.subject, p.variant)
        ]
        level = result.level or (matching[0].level if matching else None)
        prediction = next((p for p in matching if p.level == level), None) or (
            matching[0] if matching else None
        )
        predicted = prediction.predicted if prediction else None
        entries.append(
            {
                "key": catalogue.entry_key(result.subject, level, result.variant),
                "label": catalogue.label(result.subject, level, result.variant),
                "subject": result.subject,
                "level": level,
                "variant": result.variant,
                "grade": result.grade,
                "predicted": predicted,
                "va": round(result.grade - predicted, 2) if predicted is not None else None,
            }
        )
    entries.sort(key=lambda e: catalogue.sort_key(e["subject"], e["level"], e["variant"]))
    return entries, other


def _student(candidate: Any, cem: Any | None, confident: bool | None, school: str) -> dict:
    entries, other = _subject_entries(candidate, cem)
    grades = [e["grade"] for e in entries]
    vas = [e["va"] for e in entries if e["va"] is not None]
    subject_points = sum(grades) if grades else None
    checks: list[str] = []
    failing: list[rules.Condition] = []
    unchecked: list[str] = []
    core = total = None
    awarded: bool | None = None

    if candidate.pathway == "DP":
        computed_core = rules.core_points(candidate.ee_grade, candidate.tok_grade)
        core = candidate.core_points if candidate.core_points is not None else computed_core
        if None not in (candidate.core_points, computed_core) and candidate.core_points != computed_core:
            checks.append(
                f"Core points in the file ({candidate.core_points}) differ from the EE/TOK "
                f"matrix ({computed_core})."
            )
        computed_total = subject_points + (core or 0) if subject_points is not None else None
        total = candidate.total_points if candidate.total_points is not None else computed_total
        if None not in (candidate.total_points, computed_total) and candidate.total_points != computed_total:
            checks.append(
                f"Total in the file ({candidate.total_points}) differs from subject + core "
                f"points ({computed_total})."
            )
        if entries:
            failing = rules.diploma_conditions(
                [(e["level"], e["grade"]) for e in entries],
                candidate.ee_grade,
                candidate.tok_grade,
                total,
            )
            awarded = not failing
            unchecked = ["CAS"]
    elif entries:
        failing, unchecked = rules.certificate_conditions(
            grades, candidate.rp_grade, candidate.btec_result
        )
        awarded = not failing

    return {
        "name": _name(candidate),
        "school": school,
        "pathway": candidate.pathway,
        "gender": cem.gender if cem else None,
        "baseline": cem.baseline if cem else None,
        "cem_name": _name(cem) if cem else None,
        "match": None if cem is None else ("confident" if confident else "review"),
        "subjects": entries,
        "other_entries": other,
        "ee_subject": candidate.ee_subject,
        "ee_grade": candidate.ee_grade,
        "tok_grade": candidate.tok_grade,
        "rp_grade": candidate.rp_grade,
        "btec_result": candidate.btec_result,
        "notes": candidate.notes,
        "core_points": core,
        "subject_points": subject_points,
        "total_points": total,
        # DP: diploma total; CP: sum of DP course grades.
        "points": total if candidate.pathway == "DP" else subject_points,
        "average_grade": _mean(grades),
        "average_va": _mean(vas),
        "awarded": awarded,
        "failing": [{"code": c.code, "message": c.message} for c in failing],
        "unchecked": unchecked,
        "checks": checks,
        "in_cohort": bool(entries),
    }


def _va_summary(entries: list[dict]) -> dict:
    vas = [e["va"] for e in entries if e["va"] is not None]
    return {"entries": len(entries), "average_grade": _mean(e["grade"] for e in entries),
            "average_va": _mean(vas), "va_entries": len(vas)}


def _trend(points: Sequence[tuple[float, float]]) -> dict | None:
    """Least-squares line y = slope·x + intercept, with r²."""
    if len(points) < 3:
        return None
    xs, ys = zip(*points)
    mx, my = fmean(xs), fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in points)
    slope = sxy / sxx
    intercept = my - slope * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in points)
    r2 = 1 - ss_res / ss_tot if ss_tot else None
    return {
        "slope": round(slope, 4),
        "intercept": round(intercept, 4),
        "r2": round(r2, 3) if r2 is not None else None,
        "n": len(points),
    }


def _summary(students: list[dict], pathway: str) -> dict:
    entries = [e for s in students for e in s["subjects"]]
    points = [s["points"] for s in students if s["points"] is not None]
    counts = defaultdict(int)
    for e in entries:
        counts[e["grade"]] += 1
    summary: dict[str, Any] = {
        "candidates": len(students),
        "matched": sum(1 for s in students if s["cem_name"]),
        "average_points": _mean(points),
        "highest_points": max(points, default=None),
        "lowest_points": min(points, default=None),
        "average_grade": _mean(e["grade"] for e in entries),
        "average_va": _mean(e["va"] for e in entries if e["va"] is not None),
        "va_entries": sum(1 for e in entries if e["va"] is not None),
        "grade_counts": [counts[g] for g in GRADES],
        "gender": {
            g: {"candidates": sum(1 for s in students if s["gender"] == g),
                **_va_summary([e for s in students if s["gender"] == g for e in s["subjects"]])}
            for g in ("M", "F")
        },
    }
    if pathway == "dp":
        awarded = [s for s in students if s["awarded"]]
        totals = [s["total_points"] for s in students if s["total_points"] is not None]
        summary["diploma"] = {
            "awarded": len(awarded),
            "rate": _pct(len(awarded), len(students)),
            "average_points_awarded": _mean(
                s["total_points"] for s in awarded if s["total_points"] is not None
            ),
            "at_least_40": sum(1 for t in totals if t >= 40),
            "at_least_40_rate": _pct(sum(1 for t in totals if t >= 40), len(students)),
            "above_35": sum(1 for t in totals if t > 35),
            "above_35_rate": _pct(sum(1 for t in totals if t > 35), len(students)),
        }
    if pathway == "cp":
        awarded = sum(1 for s in students if s["awarded"])
        summary["certificate"] = {"awarded": awarded, "rate": _pct(awarded, len(students))}
    return summary


def _subject_stats(students: list[dict], cohort_size: int) -> dict:
    entries = [e for s in students for e in s["subjects"]]
    counts = defaultdict(int)
    for e in entries:
        counts[e["grade"]] += 1
    by_gender = {
        g: _va_summary([e for s in students if s["gender"] == g for e in s["subjects"]])
        for g in ("M", "F")
    }
    return {
        **_va_summary(entries),
        "uptake": _pct(len(entries), cohort_size),
        "grade_counts": [counts[g] for g in GRADES],
        "male": by_gender["M"],
        "female": by_gender["F"],
    }


def _only(student: dict, predicate) -> dict:
    return {**student, "subjects": [e for e in student["subjects"] if predicate(e)]}


def analyse(groups: Iterable[tuple[str, Sequence[Any], Sequence[Any]]]) -> dict:
    """`groups`: (school code, IB candidates, CEM students) per school."""
    students: list[dict] = []
    review: list[dict] = []
    unmatched_results: list[str] = []
    unmatched_cem: list[str] = []
    for school, candidates, cems in groups:
        matches = {id(m.result): m for m in match_students(list(candidates), list(cems))}
        matched_cem = {id(m.cem) for m in matches.values()}
        for candidate in candidates:
            match = matches.get(id(candidate))
            student = _student(
                candidate, match.cem if match else None, match.confident if match else None, school
            )
            students.append(student)
            if match and not match.confident:
                review.append({"name": student["name"], "cem_name": student["cem_name"]})
            if cems and not match:
                unmatched_results.append(student["name"])
        unmatched_cem += [_name(c) for c in cems if id(c) not in matched_cem]

    cohort = [s for s in students if s["in_cohort"]]
    by_pathway = {p: [s for s in cohort if _in(s, p)] for p in PATHWAYS}
    sizes = {p: len(by_pathway[p]) for p in PATHWAYS}

    entry_meta: dict[str, dict] = {}
    for s in cohort:
        for e in s["subjects"]:
            entry_meta.setdefault(e["key"], e)
    subject_rows = []
    for key, meta in sorted(
        entry_meta.items(),
        key=lambda item: catalogue.sort_key(item[1]["subject"], item[1]["level"], item[1]["variant"]),
    ):
        info = catalogue.BY_KEY[meta["subject"]]
        stats = {}
        for p in PATHWAYS:
            takers = [_only(s, lambda e: e["key"] == key) for s in by_pathway[p]]
            takers = [s for s in takers if s["subjects"]]
            stats[p] = _subject_stats(takers, sizes[p]) if takers else None
        subject_rows.append(
            {
                "key": key,
                "label": meta["label"],
                "subject": meta["subject"],
                "subject_name": info.name,
                "level": meta["level"],
                "variant": meta["variant"],
                "group": info.group,
                "stats": stats,
            }
        )

    families = []
    for key in sorted({e["subject"] for s in cohort for e in s["subjects"]}, key=catalogue.ORDER.get):
        info = catalogue.BY_KEY[key]
        stats = {}
        for p in PATHWAYS:
            entries = [e for s in by_pathway[p] for e in s["subjects"] if e["subject"] == key]
            stats[p] = _va_summary(entries) if entries else None
        families.append({"subject": key, "name": info.name, "short": info.short, "stats": stats})

    bands = []
    for label, low, high in BASELINE_BANDS:
        row = {"band": label, "stats": {}}
        for p in PATHWAYS:
            members = [
                s for s in by_pathway[p] if s["baseline"] is not None and low <= s["baseline"] < high
            ]
            row["stats"][p] = {
                "candidates": len(members),
                **_va_summary([e for s in members for e in s["subjects"]]),
            }
        bands.append(row)

    scatter = [
        {
            "name": s["name"],
            "pathway": s["pathway"],
            "baseline": s["baseline"],
            "points": s["points"],
            "average_grade": s["average_grade"],
            "average_va": s["average_va"],
        }
        for s in cohort
        if s["baseline"] is not None
    ]
    trend = {
        "dp": _trend([(p["baseline"], p["points"]) for p in scatter
                      if p["pathway"] == "DP" and p["points"] is not None]),
        "cp": _trend([(p["baseline"], p["average_grade"]) for p in scatter
                      if p["pathway"] == "CP" and p["average_grade"] is not None]),
    }

    return {
        "summary": {p: _summary(by_pathway[p], p) for p in PATHWAYS},
        "subjects": subject_rows,
        "families": families,
        "baseline_bands": bands,
        "scatter": scatter,
        "trend": trend,
        "students": sorted(students, key=lambda s: (s["pathway"], s["name"].lower())),
        "matching": {
            "matched": sum(1 for s in students if s["cem_name"]),
            "review": review,
            "unmatched_results": sorted(unmatched_results),
            "unmatched_cem": sorted(unmatched_cem),
        },
        "va_threshold": rules.VA_THRESHOLD,
    }
