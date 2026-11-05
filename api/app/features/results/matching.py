"""Match IB results candidates to CEM baseline students by name.

The workbooks have no shared student ID and write names differently
("Abdirahman, Rahma" vs "Rahama Abdirahman"), so matching is by surname plus
first-name similarity, one-to-one. Surname-only matches are flagged for review.
"""

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Generic, Protocol, TypeVar

FIRST_NAME_THRESHOLD = 0.8


class Named(Protocol):
    first_name: str
    last_name: str


A = TypeVar("A", bound=Named)
B = TypeVar("B", bound=Named)


@dataclass
class Match(Generic[A, B]):
    result: A
    cem: B
    # False when only the surname matched (e.g. a nickname); shown for review.
    confident: bool


def tokens(text: str) -> list[str]:
    """Lowercase ASCII name parts. "?" is kept: CEM exports lose accents that way."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    ascii_text = re.sub(r"['’`]", "", ascii_text.lower())
    return [t for t in re.split(r"[^a-z?]+", ascii_text) if t]


def _pattern(token: str) -> re.Pattern[str]:
    return re.compile("".join(".{0,2}" if ch == "?" else re.escape(ch) for ch in token))


def _same(a: str, b: str) -> bool:
    if a == b:
        return True
    if "?" in a:
        return _pattern(a).fullmatch(b) is not None
    if "?" in b:
        return _pattern(b).fullmatch(a) is not None
    return False


def _similarity(a: str, b: str) -> float:
    if _same(a, b):
        return 1.0
    if len(a) < 3 or len(b) < 3:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _score(result: Named, cem: Named) -> tuple[int, float] | None:
    """(surname parts matched, best first-name similarity), or None without a surname match."""
    result_tokens = tokens(f"{result.first_name} {result.last_name}")
    surname = [t for t in tokens(cem.last_name) if len(t) >= 2]
    matched = [t for t in surname if any(_same(t, r) for r in result_tokens)]
    if not matched:
        return None
    rest = [r for r in result_tokens if not any(_same(t, r) for t in matched)]
    first = max(
        (_similarity(f, r) for f in tokens(cem.first_name) for r in rest), default=0.0
    )
    return len(matched), first


def match_students(results: list[A], cems: list[B]) -> list[Match[A, B]]:
    scored: list[tuple[tuple[int, float], int, int]] = []
    surname_hits_result: dict[int, int] = {}
    surname_hits_cem: dict[int, int] = {}
    for i, result in enumerate(results):
        for j, cem in enumerate(cems):
            score = _score(result, cem)
            if score is None:
                continue
            scored.append((score, i, j))
            surname_hits_result[i] = surname_hits_result.get(i, 0) + 1
            surname_hits_cem[j] = surname_hits_cem.get(j, 0) + 1

    matches: list[Match[A, B]] = []
    used_results: set[int] = set()
    used_cems: set[int] = set()
    for (_, first), i, j in sorted(scored, key=lambda s: s[0], reverse=True):
        if i in used_results or j in used_cems:
            continue
        confident = first >= FIRST_NAME_THRESHOLD
        # A surname-only match is accepted only when it is unambiguous both ways.
        if not confident and (surname_hits_result[i] > 1 or surname_hits_cem[j] > 1):
            continue
        used_results.add(i)
        used_cems.add(j)
        matches.append(Match(results[i], cems[j], confident))
    return matches
