import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

# Must match the curriculum slugs used by the UI (ui/src/app/core/curriculum/curricula.ts).
CURRICULUM_SLUGS = ("ib", "igcse", "a-level")
# "all" is the dashboard's group-wide view, so no school may use it as a code.
RESERVED_CODES = frozenset({"all"})
_CODE_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,18}[a-z0-9])?$")


def normalize_code(value: str) -> str:
    code = value.strip().lower()
    if not _CODE_PATTERN.fullmatch(code):
        raise ValueError(
            "code must be 1-20 lowercase letters, digits or hyphens, "
            "starting and ending with a letter or digit"
        )
    if code in RESERVED_CODES:
        raise ValueError(f"'{code}' is reserved")
    return code


def normalize_curricula(values: list[str]) -> list[str]:
    curricula: list[str] = []
    for value in values:
        slug = value.strip().lower()
        if slug not in CURRICULUM_SLUGS:
            raise ValueError(
                f"unknown curriculum '{value}'; expected one of {', '.join(CURRICULUM_SLUGS)}"
            )
        if slug not in curricula:
            curricula.append(slug)
    return curricula


SchoolCode = Annotated[str, AfterValidator(normalize_code)]
Curricula = Annotated[list[str], AfterValidator(normalize_curricula)]
SchoolName = Annotated[str, Field(min_length=1, max_length=255)]


class SchoolCreate(BaseModel):
    code: SchoolCode
    name: SchoolName
    curricula: Curricula = Field(default_factory=list)


class SchoolUpdate(BaseModel):
    name: SchoolName | None = None
    curricula: Curricula | None = None
    is_active: bool | None = None


class SchoolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    curricula: list[str]
    is_active: bool
