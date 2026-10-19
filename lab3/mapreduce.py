import argparse
import csv
import io
import time
from collections import Counter

from lib import config
from lib.io_util import print_top, write_counts
from lib.rustfs import s3_client
from lib.variant import emit_counts, is_frontend, parse_skills


def read_chunk(client, start: int, end: int) -> bytes:
    rng = f"bytes={start}-{end}"
    return client.get_object(
        Bucket=config.BUCKET, Key=config.RAW_KEY, Range=rng
    )["Body"].read()



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--optimized",
        action="store_true",
    )
    args = parser.parse_args()
    chunk = config.CHUNK_SIZE_OPTIMIZED if args.optimized else config.CHUNK_SIZE

    client = s3_client()
    size = client.head_object(Bucket=config.BUCKET, Key=config.RAW_KEY)["ContentLength"]
    print(f"S3 object size: {size} bytes, chunk={chunk} bytes, optimized={args.optimized}")

    c1, c2, c3 = Counter(), Counter(), Counter()
    matched = 0 

    header = None 
    idx_role = idx_name = idx_skills = 0
    carry = ""
    start = 0
    t0 = time.perf_counter()

    while start < size:
        end = min(start + chunk - 1, size - 1)
        text = carry + read_chunk(client, start, end).decode("utf-8", errors="replace")

        if end < size - 1:
            cut = text.rfind("\n")
            if cut == -1:
                carry = text
                start = end + 1
                continue
            carry, text = text[cut + 1 :], text[:cut]
        else:
            carry = ""

        buf = io.StringIO(text)

        if header is None:
            header_row = next(csv.reader(buf))
            header = {name: i for i, name in enumerate(header_row)}
            idx_role = header["role"]
            idx_name = header["name"]
            idx_skills = header["key_skills"]

        need = max(idx_role, idx_name, idx_skills)

        for row in csv.reader(buf):
            if len(row) <= need:
                continue
            if not is_frontend(row[idx_role], row[idx_name]):
                continue
            skills = parse_skills(row[idx_skills])
            if not skills:
                continue
            matched += 1
            emit_counts(skills, c1, c2, c3)

        start = end + 1
        print(f"  read {end + 1}/{size} ({100 * (end + 1) / size:.1f}%)", flush=True)

    elapsed = time.perf_counter() - t0
    for name, counter in (
        ("skills_1.csv", c1),
        ("skills_2.csv", c2),
        ("skills_3.csv", c3),
    ):
        local = config.RESULTS / name
        write_counts(local, counter)
        key = f"{config.RESULTS_PREFIX}/{name}"
        client.upload_file(str(local), config.BUCKET, key)
        print(f"uploaded s3://{config.BUCKET}/{key}  unique={len(counter)}")

    print(f"matched vacancies: {matched}")
    print(f"elapsed_sec: {elapsed:.1f}")
    print_top(c1, "top-5 singles:")
    print_top(c2, "top-5 pairs:")
    print_top(c3, "top-5 triples:")


if __name__ == "__main__":
    main()
