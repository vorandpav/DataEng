import time

from lib import config
from lib.rustfs import duckdb_s3
from lib.variant import SQL_SKILLS_LIST, SQL_VARIANT_WHERE


def print_top_csv(con, path: str, title: str) -> None:
    print(title)
    rows = con.execute(f"""
        SELECT key, count FROM read_csv_auto('{path}')
        ORDER BY count DESC LIMIT 5
    """).fetchall()
    for key, count in rows:
        print(f"  {count}\t{key}")


def main() -> None:
    con = duckdb_s3()
    print(f"reading {config.S3_CSV} via RustFS httpfs")
    t0 = time.perf_counter()

    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE frontend AS
    SELECT {SQL_SKILLS_LIST} AS sk
    FROM read_csv_auto('{config.S3_CSV}', header=true, ignore_errors=true)
    WHERE {SQL_VARIANT_WHERE}
      AND key_skills IS NOT NULL AND key_skills <> '';
    """)

    queries = {
        1: """
            SELECT s AS key, count(*) AS count
            FROM frontend, UNNEST(sk) AS u(s)
            GROUP BY 1 ORDER BY 1
        """,
        2: """
            SELECT s1 || '|' || s2 AS key, count(*) AS count
            FROM frontend, UNNEST(sk) AS u1(s1), UNNEST(sk) AS u2(s2)
            WHERE s1 < s2
            GROUP BY 1 ORDER BY 1
        """,
        3: """
            SELECT s1 || '|' || s2 || '|' || s3 AS key, count(*) AS count
            FROM frontend,
                 UNNEST(sk) AS u1(s1), UNNEST(sk) AS u2(s2), UNNEST(sk) AS u3(s3)
            WHERE s1 < s2 AND s2 < s3
            GROUP BY 1 ORDER BY 1
        """,
    }

    for size, sql in queries.items():
        path = (config.RESULTS / f"duckdb_skills_{size}.csv").as_posix()
        con.execute(f"COPY ({sql}) TO '{path}' (HEADER, DELIMITER ',');")
        uniq = con.execute(
            f"SELECT count(*) FROM read_csv_auto('{path}')"
        ).fetchone()[0]
        print(f"wrote {path}  unique={uniq}")

    n = con.execute("SELECT count(*) FROM frontend").fetchone()[0]
    print(f"matched vacancies: {n}")
    print(f"elapsed_sec: {time.perf_counter() - t0:.1f}")
    print_top_csv(con, (config.RESULTS / "duckdb_skills_1.csv").as_posix(), "top-5 singles:")
    print_top_csv(con, (config.RESULTS / "duckdb_skills_2.csv").as_posix(), "top-5 pairs:")
    print_top_csv(con, (config.RESULTS / "duckdb_skills_3.csv").as_posix(), "top-5 triples:")


if __name__ == "__main__":
    main()
