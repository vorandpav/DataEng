import csv
import re

from tabulate import tabulate

from lib import config
from lib.rustfs import duckdb_s3
from lib.variant import SQL_SKILLS_LIST, SQL_VARIANT_WHERE


def slug(name: str) -> str:
    return re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_")


def main() -> None:
    con = duckdb_s3()
    print(f"reading {config.S3_CSV} via RustFS httpfs")

    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE fe AS
    SELECT
      area,
      {SQL_SKILLS_LIST} AS sk,
      CASE
        WHEN currency = 'RUR' AND salary_from IS NOT NULL AND salary_to IS NOT NULL
          THEN (salary_from + salary_to) / 2.0
        WHEN currency = 'RUR' AND salary_from IS NOT NULL THEN salary_from
        WHEN currency = 'RUR' AND salary_to IS NOT NULL THEN salary_to
        ELSE NULL
      END AS salary
    FROM read_csv_auto('{config.S3_CSV}', header=true, ignore_errors=true)
    WHERE {SQL_VARIANT_WHERE};
    """)

    top_areas = con.execute("""
        SELECT area, count(*) AS n
        FROM fe
        WHERE area IS NOT NULL AND area <> ''
        GROUP BY 1
        ORDER BY n DESC
        LIMIT 3
    """).fetchall()

    print("\n=== top-3 regions by Frontend volume ===")
    print(tabulate(top_areas, headers=["area", "n"], tablefmt="simple"))

    summary_rows = []
    for area, _ in top_areas:
        safe = area.replace("'", "''")

        n, med, mean, with_sal = con.execute(f"""
            SELECT count(*), median(salary), avg(salary), count(salary)
            FROM fe WHERE area = '{safe}'
        """).fetchone()
        summary_rows.append([
            area,
            n,
            with_sal,
            None if med is None else round(med),
            None if mean is None else round(mean),
        ])

        queries = {
            "skills": f"""
                SELECT s AS key, count(*) AS c
                FROM fe, UNNEST(sk) u(s)
                WHERE area = '{safe}' AND len(sk) > 0
                GROUP BY 1 ORDER BY c DESC LIMIT {config.REGION_TOP_SKILLS}
            """,
            "pairs": f"""
                SELECT s1 || '|' || s2 AS key, count(*) AS c
                FROM fe, UNNEST(sk) u1(s1), UNNEST(sk) u2(s2)
                WHERE area = '{safe}' AND s1 < s2
                GROUP BY 1 ORDER BY c DESC LIMIT {config.REGION_TOP_SKILLS}
            """,
            "triples": f"""
                SELECT s1 || '|' || s2 || '|' || s3 AS key, count(*) AS c
                FROM fe, UNNEST(sk) u1(s1), UNNEST(sk) u2(s2), UNNEST(sk) u3(s3)
                WHERE area = '{safe}' AND s1 < s2 AND s2 < s3
                GROUP BY 1 ORDER BY c DESC LIMIT {config.REGION_TOP_SKILLS}
            """,
        }
        for label, sql in queries.items():
            rows = con.execute(sql).fetchall()
            out = config.RESULTS / f"regions_{slug(area)}_{label}.csv"
            with out.open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["key", "count"])
                w.writerows(rows)
            print(f"\n=== {area} — top {label} ===")
            print(tabulate(rows, headers=["key", "count"], tablefmt="simple"))

    print("\n=== region salary summary (RUR where present) ===")
    print(tabulate(
        summary_rows,
        headers=["area", "vacancies", "with_salary", "median", "mean"],
        tablefmt="simple",
    ))
    with (config.RESULTS / "regions_summary.csv").open(
        "w", encoding="utf-8", newline=""
    ) as f:
        w = csv.writer(f)
        w.writerow(["area", "vacancies", "with_salary", "median", "mean"])
        w.writerows(summary_rows)

if __name__ == "__main__":
    main()
