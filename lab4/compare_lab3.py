import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "lab3"))
from lib.io_util import load_counts

from lib import paths


def main() -> None:
    ref = paths.LAB3_PAIRS
    got = paths.RESULTS / (sys.argv[1] if len(sys.argv) > 1 else "pairs_A.csv")

    a, b = load_counts(ref), load_counts(got)
    if a == b:
        print(f"OK: совпадает с lab3 ({len(a)} keys, sum={sum(a.values())})")
        return
    print("FAIL: расхождение с lab3")
    sys.exit(1)


if __name__ == "__main__":
    main()
