import csv
from collections import Counter
from pathlib import Path


def write_counts(path: Path, counter: Counter) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["key", "count"])
        for key, count in sorted(counter.items()):
            w.writerow([key, count])


def load_counts(path: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[row["key"]] = int(row["count"])
    return out


def print_top(counter: Counter, title: str, n: int = 5) -> None:
    print(title)
    for key, count in counter.most_common(n):
        print(f"  {count}\t{key}")
