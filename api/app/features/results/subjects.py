"""IB subject catalogue: maps workbook abbreviations and CEM subject names to one key.

Labels follow the school's analysis report, e.g. "Eng HL", "Fre Ab", "Mat SL AI".
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Subject:
    key: str
    short: str
    name: str
    group: int
    # Language B subjects that can also be taken ab initio.
    has_ab_initio: bool = False
    # Mathematics: Analysis & Approaches ("aa") or Applications & Interpretation ("ai").
    is_maths: bool = False


SUBJECTS: tuple[Subject, ...] = (
    Subject("eng", "Eng", "English A", 1),
    Subject("swe", "Swe", "Swedish", 1),
    Subject("fre", "Fre", "French", 2, has_ab_initio=True),
    Subject("spa", "Spa", "Spanish", 2, has_ab_initio=True),
    Subject("swa", "Swa", "Kiswahili", 2, has_ab_initio=True),
    Subject("bus", "Bus", "Business Management", 3),
    Subject("eco", "Eco", "Economics", 3),
    Subject("his", "His", "History", 3),
    Subject("psy", "Psy", "Psychology", 3),
    Subject("ds", "DS", "Digital Society", 3),
    Subject("ess", "ESS", "Environmental Systems & Societies", 4),
    Subject("sehs", "SEHS", "Sports, Exercise & Health Science", 4),
    Subject("bio", "Bio", "Biology", 4),
    Subject("che", "Che", "Chemistry", 4),
    Subject("phy", "Phy", "Physics", 4),
    Subject("mat", "Mat", "Mathematics", 5, is_maths=True),
    Subject("art", "Art", "Visual Arts", 6),
    Subject("dra", "Theatre", "Theatre", 6),
    Subject("mus", "Mus", "Music", 6),
)

BY_KEY = {s.key: s for s in SUBJECTS}
ORDER = {s.key: i for i, s in enumerate(SUBJECTS)}

# Column headings used in the IB results workbook.
_RESULT_ABBREVIATIONS = {
    "eng": "eng",
    "fre": "fre",
    "spa": "spa",
    "swa": "swa",
    "swe": "swe",
    "bus": "bus",
    "eco": "eco",
    "his": "his",
    "psy": "psy",
    "ds": "ds",
    "itgs": "ds",
    "ess": "ess",
    "sehs": "sehs",
    "bio": "bio",
    "che": "che",
    "chem": "che",
    "phy": "phy",
    "mat": "mat",
    "math": "mat",
    "maths": "mat",
    "art": "art",
    "dra": "dra",
    "theatre": "dra",
    "mus": "mus",
    "music": "mus",
}

# Prefixes of CEM subject names (lowercase, after "IB-H-" / "IB-S-").
_CEM_PREFIXES = (
    ("english", "eng"),
    ("swedish", "swe"),
    ("french", "fre"),
    ("spanish", "spa"),
    ("kiswahili", "swa"),
    ("swahili", "swa"),
    ("business", "bus"),
    ("economics", "eco"),
    ("history", "his"),
    ("psychology", "psy"),
    ("information technology in a global", "ds"),
    ("digital society", "ds"),
    ("environmental systems", "ess"),
    ("sports exercise", "sehs"),
    ("sports, exercise", "sehs"),
    ("biology", "bio"),
    ("chemistry", "che"),
    ("physics", "phy"),
    ("mathematics", "mat"),
    ("visual arts", "art"),
    ("theatre", "dra"),
    ("music", "mus"),
)

# Subjects whose prediction stands in, in order, when CEM has none for the
# subject itself (CEM doesn't predict ESS or the arts).
PROXIES: dict[str, tuple[str, ...]] = {
    "ess": ("bio",),
    "art": ("dra", "mus"),
    "dra": ("mus", "art"),
    "mus": ("dra", "art"),
}
# Groups where, once the listed proxies are exhausted, any other subject in
# the same group can stand in.
GROUP_FALLBACK = frozenset({6})

_CEM_SUBJECT = re.compile(r"^IB-([HS])-(.+)$", re.IGNORECASE)
_HEADING = re.compile(r"^([a-z&]+)(?:\s+(hl|sl|ab))?(?:\s+(aa|ai))?$")

LEVEL_ORDER = {"HL": 0, "SL": 1, None: 2}


def result_heading(value: object) -> tuple[str, str | None, str | None] | None:
    """Parse a results column heading such as "Bio" or "Mat SL AI".

    Returns (subject key, level, variant); level and variant are None when the
    heading does not say, as in the sample workbook.
    """
    if not isinstance(value, str):
        return None
    match = _HEADING.fullmatch(" ".join(value.lower().split()))
    if not match:
        return None
    key = _RESULT_ABBREVIATIONS.get(match.group(1))
    if key is None:
        return None
    level = match.group(2)
    variant = match.group(3)
    if level == "ab":
        return key, "SL", "ab"
    return key, level.upper() if level else None, variant


def cem_subject(value: str) -> tuple[str | None, str, str | None]:
    """Parse a CEM subject such as "IB-S-French_ab_initio".

    Returns (subject key or None if unknown, level, variant).
    Raises ValueError if the value is not in the IB-H-/IB-S- format.
    """
    match = _CEM_SUBJECT.fullmatch(value.strip())
    if not match:
        raise ValueError(f"'{value}' is not a CEM IB subject (expected IB-H-… or IB-S-…)")
    level = "HL" if match.group(1).upper() == "H" else "SL"
    name = " ".join(match.group(2).replace("_", " ").lower().split())
    key = next((k for prefix, k in _CEM_PREFIXES if name.startswith(prefix)), None)
    variant = None
    if key and BY_KEY[key].has_ab_initio and "ab initio" in name:
        variant = "ab"
    elif key == "mat":
        if "analysis" in name:
            variant = "aa"
        elif "application" in name:
            variant = "ai"
    return key, level, variant


def label(key: str, level: str | None, variant: str | None) -> str:
    short = BY_KEY[key].short if key in BY_KEY else key
    if variant == "ab":
        return f"{short} Ab"
    parts = [short]
    if level:
        parts.append(level)
    if variant in ("aa", "ai"):
        parts.append(variant.upper())
    return " ".join(parts)


def entry_key(key: str, level: str | None, variant: str | None) -> str:
    return "-".join(p for p in (key, (level or "").lower(), variant or "") if p)


def sort_key(key: str, level: str | None, variant: str | None) -> tuple:
    return (ORDER.get(key, len(ORDER)), variant == "ab", LEVEL_ORDER[level], variant or "")


def prediction_matches(
    result_key: str, result_variant: str | None, pred_key: str | None, pred_variant: str | None
) -> bool:
    """Whether a CEM prediction applies to a result in the same subject."""
    if pred_key != result_key:
        return False
    subject = BY_KEY.get(result_key)
    if subject and subject.has_ab_initio:
        return (pred_variant == "ab") == (result_variant == "ab")
    if subject and subject.is_maths and pred_variant and result_variant:
        return pred_variant == result_variant
    return True


def proxy_subjects(key: str) -> tuple[str, ...]:
    """Subjects whose CEM prediction may stand in for `key`, most preferred first."""
    proxies = list(PROXIES.get(key, ()))
    subject = BY_KEY.get(key)
    if subject and subject.group in GROUP_FALLBACK:
        proxies += [s.key for s in SUBJECTS if s.group == subject.group and s.key not in (key, *proxies)]
    return tuple(proxies)
