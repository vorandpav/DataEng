import sys

from lib import config
from lib.io_util import load_counts


def compare(label: str, path_a, path_b) -> bool:
    a, b = load_counts(path_a), load_counts(path_b)
    if a == b:
        print(f"OK {label}: keys={len(a)}  sum={sum(a.values())}")
        return True
    print(f"FAIL {label}")
    return False


def main() -> None:
    ok = True
    for i in (1, 2, 3):
        ok &= compare(
            f"skills_{i}",
            config.RESULTS / f"skills_{i}.csv",
            config.RESULTS / f"duckdb_skills_{i}.csv",
        )
    if not ok:
        sys.exit(1)
    print("ALL MATCH")


if __name__ == "__main__":
    main()
