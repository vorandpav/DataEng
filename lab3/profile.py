import csv
import subprocess
import sys
import time
from collections import defaultdict

import psutil

from lib import config

RUNS = 3
ROOT = config.ROOT


def run_once(label: str, args: list[str]) -> tuple[float, float]:
    proc = subprocess.Popen(
        [sys.executable, *args],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    p = psutil.Process(proc.pid)
    peak = 0
    t0 = time.perf_counter()

    while proc.poll() is None:
        try:
            rss = p.memory_info().rss
            for ch in p.children(recursive=True):
                try:
                    rss += ch.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            peak = max(peak, rss)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        time.sleep(0.05)

    elapsed = time.perf_counter() - t0
    if proc.returncode != 0:
        raise RuntimeError(f"{label} failed with code {proc.returncode}")
    return elapsed, peak / (1024 * 1024)


def main() -> None:
    jobs = [
        ("mapreduce", ["mapreduce.py"]),
        ("duckdb", ["duckdb_skills.py"]),
        ("mapreduce_opt", ["mapreduce.py", "--optimized"]),
    ]
    rows: list[list] = []

    for label, args in jobs:
        for attempt in range(1, RUNS + 1):
            print(f"run {label} #{attempt} ...", flush=True)
            sec, mb = run_once(label, args)
            print(f"  {sec:.1f}s  peak_rss={mb:.0f} MB")
            rows.append([label, attempt, round(sec, 2), round(mb, 1)])

    out = config.RESULTS / "profiling.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["label", "attempt", "seconds", "peak_rss_mb"])
        w.writerows(rows)

    print(f"\nwrote {out}")
    print("\nsummary (mean):")
    agg: dict[str, list] = defaultdict(lambda: [[], []])
    for label, _, sec, mb in rows:
        agg[label][0].append(sec)
        agg[label][1].append(mb)
    for label, (secs, mbs) in agg.items():
        print(
            f"  {label}: time={sum(secs)/len(secs):.1f}s  "
            f"rss={sum(mbs)/len(mbs):.0f} MB"
        )


if __name__ == "__main__":
    main()
