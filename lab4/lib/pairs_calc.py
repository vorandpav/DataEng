import csv
import io
import json
import sys
import time
import zlib
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lab3"))
from lib.variant import emit_counts, is_frontend, parse_skills

CHUNK = 16 * 1024 * 1024


def empty_counters() -> tuple[Counter, Counter, Counter]:
    return Counter(), Counter(), Counter()


def _header_indexes(csv_path: Path) -> tuple[int, int, int]:
    with csv_path.open(encoding="utf-8", newline="") as f:
        row = next(csv.reader(f))
    h = {n: i for i, n in enumerate(row)}
    return h["role"], h["name"], h["key_skills"]


def load_checkpoint(
    raw: bytes | None,
) -> tuple[int, tuple[Counter, Counter, Counter]]:
    if not raw:
        return 0, empty_counters()

    data = json.loads(zlib.decompress(raw).decode("utf-8"))

    counters = (
        Counter(data["singles"]),
        Counter(data["pairs"]),
        Counter(data["triples"]),
    )
    return int(data["offset"]), counters


def dump_checkpoint(
    offset: int,
    counters: tuple[Counter, Counter, Counter],
) -> bytes:
    c1, c2, c3 = counters
    payload = json.dumps(
        {
            "offset": offset,
            "singles": dict(c1),
            "pairs": dict(c2),
            "triples": dict(c3),
        },
        ensure_ascii=False,
    ).encode("utf-8")
    return zlib.compress(payload)


def run_counts(
    csv_path: Path,
    start_offset: int,
    counters: tuple[Counter, Counter, Counter],
    on_chunk,
    throttle_sec: float = 0.0,
    should_abort=None,
) -> tuple[Counter, Counter, Counter]:
    size = csv_path.stat().st_size
    idx_role, idx_name, idx_skills = _header_indexes(csv_path)
    need = max(idx_role, idx_name, idx_skills)

    c1, c2, c3 = counters
    carry = b""
    start = start_offset

    while start < size:
        if should_abort and should_abort():
            break

        end = min(start + CHUNK - 1, size - 1)
        with csv_path.open("rb") as f:
            f.seek(start)
            body = f.read(end - start + 1)

        raw = carry + body

        if end < size - 1:
            cut = raw.rfind(b"\n")
            if cut == -1:
                carry = raw
                start = end + 1
                continue

            carry = raw[cut + 1:]
            complete_text = raw[:cut + 1].decode("utf-8")
            safe_offset = end + 1 - len(carry)
        else:
            complete_text = raw.decode("utf-8")
            carry = b""
            safe_offset = end + 1

        for row in csv.reader(io.StringIO(complete_text)):
            if len(row) <= need:
                continue
            if not is_frontend(row[idx_role], row[idx_name]):
                continue

            skills = parse_skills(row[idx_skills])
            if not skills:
                continue

            emit_counts(skills, c1, c2, c3)

        on_chunk(safe_offset, (c1, c2, c3))
        start = end + 1

        if throttle_sec > 0:
            time.sleep(throttle_sec)

    return c1, c2, c3


def control_line(
    counters: tuple[Counter, Counter, Counter],
) -> str:
    c1, c2, c3 = counters
    return (
        f"singles: keys={len(c1)} sum={sum(c1.values())}; "
        f"pairs: keys={len(c2)} sum={sum(c2.values())}; "
        f"triples: keys={len(c3)} sum={sum(c3.values())}"
    )


def write_counts_csv(path: Path, counter: Counter) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["key", "count"])
        for key, value in sorted(counter.items()):
            w.writerow([key, value])


def write_all_csv(
    results_dir: Path,
    coordinator_id: str,
    counters: tuple[Counter, Counter, Counter],
) -> tuple[Path, Path, Path]:
    c1, c2, c3 = counters

    singles_path = results_dir / f"singles_{coordinator_id}.csv"
    pairs_path = results_dir / f"pairs_{coordinator_id}.csv"
    triples_path = results_dir / f"triples_{coordinator_id}.csv"

    write_counts_csv(singles_path, c1)
    write_counts_csv(pairs_path, c2)
    write_counts_csv(triples_path, c3)

    return singles_path, pairs_path, triples_path
