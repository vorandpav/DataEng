from tabulate import tabulate

from lib import config
from lib.rustfs import duckdb_s3
from lib.variant import SQL_SKILLS_LIST, SQL_VARIANT_WHERE

PAIRS_SQL = """
WITH sets AS (
  SELECT s1 || '|' || s2 AS skills, s1, s2,
         median(salary) AS set_median, count(*) AS support
  FROM v, UNNEST(sk) u1(s1), UNNEST(sk) u2(s2)
  WHERE s1 < s2
  GROUP BY 1, 2, 3
  HAVING count(*) >= {support}
),
with_base AS (
  SELECT skills, set_median, support,
    CASE WHEN f1.c >= f2.c THEN s1 ELSE s2 END AS baseline_skill,
    CASE WHEN f1.c >= f2.c THEN m1.med ELSE m2.med END AS baseline_median
  FROM sets
  JOIN freq f1 ON f1.skill = s1
  JOIN freq f2 ON f2.skill = s2
  JOIN single_med m1 ON m1.skill = s1
  JOIN single_med m2 ON m2.skill = s2
)
SELECT skills, round(set_median) AS set_median,
       baseline_skill, round(baseline_median) AS baseline_median,
       round(set_median - baseline_median) AS lift, support
FROM with_base
"""

TRIPLES_SQL = """
WITH sets AS (
  SELECT s1 || '|' || s2 || '|' || s3 AS skills, s1, s2, s3,
         median(salary) AS set_median, count(*) AS support
  FROM v, UNNEST(sk) u1(s1), UNNEST(sk) u2(s2), UNNEST(sk) u3(s3)
  WHERE s1 < s2 AND s2 < s3
  GROUP BY 1, 2, 3, 4
  HAVING count(*) >= {support}
),
ranked AS (
  SELECT sets.*, f1.c AS c1, f2.c AS c2, f3.c AS c3,
         m1.med AS med1, m2.med AS med2, m3.med AS med3
  FROM sets
  JOIN freq f1 ON f1.skill = s1
  JOIN freq f2 ON f2.skill = s2
  JOIN freq f3 ON f3.skill = s3
  JOIN single_med m1 ON m1.skill = s1
  JOIN single_med m2 ON m2.skill = s2
  JOIN single_med m3 ON m3.skill = s3
),
with_base AS (
  SELECT skills, set_median, support,
    CASE WHEN c1 >= c2 AND c1 >= c3 THEN s1
         WHEN c2 >= c1 AND c2 >= c3 THEN s2 ELSE s3 END AS baseline_skill,
    CASE WHEN c1 >= c2 AND c1 >= c3 THEN med1
         WHEN c2 >= c1 AND c2 >= c3 THEN med2 ELSE med3 END AS baseline_median
  FROM ranked
)
SELECT skills, round(set_median) AS set_median,
       baseline_skill, round(baseline_median) AS baseline_median,
       round(set_median - baseline_median) AS lift, support
FROM with_base
"""


def dump(con, name: str, sql: str, order: str) -> None:
    path = (config.RESULTS / name).as_posix()
    con.execute(f"""
    COPY (
      SELECT * FROM ({sql.format(support=config.SALARY_SUPPORT)})
      ORDER BY lift {order}
      LIMIT {config.SALARY_TOP}
    ) TO '{path}' (HEADER, DELIMITER ',');
    """)
    rows = con.execute(f"SELECT * FROM read_csv_auto('{path}')").fetchall()
    print(f"\n=== {name} ===")
    print(tabulate(
        rows,
        headers=["skills", "set_med", "base", "base_med", "lift", "n"],
        tablefmt="simple",
    ))


def main() -> None:
    con = duckdb_s3()
    print(f"reading {config.S3_CSV} via RustFS httpfs")

    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE v AS
    SELECT
      {SQL_SKILLS_LIST} AS sk,
      CASE
        WHEN salary_from IS NOT NULL AND salary_to IS NOT NULL
          THEN (salary_from + salary_to) / 2.0
        WHEN salary_from IS NOT NULL THEN salary_from
        ELSE salary_to
      END AS salary
    FROM read_csv_auto('{config.S3_CSV}', header=true, ignore_errors=true)
    WHERE {SQL_VARIANT_WHERE}
      AND currency = 'RUR'
      AND (salary_from IS NOT NULL OR salary_to IS NOT NULL)
      AND key_skills IS NOT NULL AND key_skills <> '';
    """)

    n = con.execute("SELECT count(*) FROM v").fetchone()[0]
    print(f"Frontend + RUR + salary: {n} vacancies")

    con.execute("""
    CREATE OR REPLACE TEMP TABLE freq AS
    SELECT s AS skill, count(*) AS c FROM v, UNNEST(sk) AS u(s) GROUP BY 1;
    """)
    con.execute("""
    CREATE OR REPLACE TEMP TABLE single_med AS
    SELECT s AS skill, median(salary) AS med FROM v, UNNEST(sk) AS u(s) GROUP BY 1;
    """)

    dump(con, "salary_pairs_up.csv", PAIRS_SQL, "DESC")
    dump(con, "salary_pairs_down.csv", PAIRS_SQL, "ASC")
    dump(con, "salary_triples_up.csv", TRIPLES_SQL, "DESC")
    dump(con, "salary_triples_down.csv", TRIPLES_SQL, "ASC")


if __name__ == "__main__":
    main()
