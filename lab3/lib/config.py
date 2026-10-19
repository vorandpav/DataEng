from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
DATA_CSV = ROOT / "data" / "it_vacancies_2024.csv"

S3_ENDPOINT = "http://127.0.0.1:9000"
S3_ACCESS_KEY = "hhadmin"
S3_SECRET_KEY = "hhadmin-secret"
S3_REGION = "us-east-1"

BUCKET = "hh-lake"
RAW_KEY = "raw/it_vacancies_2024.csv"
S3_CSV = f"s3://{BUCKET}/{RAW_KEY}"
RESULTS_PREFIX = "results/frontend"

CHUNK_SIZE = 16 * 1024 * 1024
CHUNK_SIZE_OPTIMIZED = 64 * 1024 * 1024

SALARY_SUPPORT = 30
SALARY_TOP = 10
REGION_TOP_SKILLS = 10

RESULTS.mkdir(exist_ok=True)
