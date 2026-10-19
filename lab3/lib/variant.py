import re
from collections import Counter
from itertools import combinations

ROLE_TARGET = "Программист, разработчик"

NAME_REGEX = re.compile(
    r"(Frontend|Front-end|Front end|фронтенд|фронт-енд)",
    re.IGNORECASE,
)

SQL_NAME_PATTERN = r"(?i)(Frontend|Front-end|Front end|фронтенд|фронт-енд)"
SQL_VARIANT_WHERE = f"""
  role = '{ROLE_TARGET}'
  AND regexp_matches(name, '{SQL_NAME_PATTERN}')
"""

SQL_SKILLS_LIST = """
  list_distinct(
    list_filter(
      list_transform(string_split(COALESCE(key_skills, ''), ';'), x -> trim(x)),
      x -> x <> ''
    )
  )
"""


def is_frontend(role: str | None, name: str | None) -> bool:
    if role != ROLE_TARGET or not name:
        return False
    return bool(NAME_REGEX.search(name))


def parse_skills(raw: str | None) -> list[str]:
    if not raw:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for part in raw.split(";"):
        skill = part.strip()
        if skill and skill not in seen:
            seen.add(skill)
            out.append(skill)
    return out


def emit_counts(skills: list[str], c1: Counter, c2: Counter, c3: Counter) -> None:
    c1.update(skills)
    for a, b in combinations(skills, 2):
        c2["|".join(sorted((a, b)))] += 1
    for a, b, c in combinations(skills, 3):
        c3["|".join(sorted((a, b, c)))] += 1
