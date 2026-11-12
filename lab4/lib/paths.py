from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB3_ROOT = ROOT.parent / "lab3"
CSV = LAB3_ROOT / "data" / "it_vacancies_2024.csv"
LAB3_PAIRS = LAB3_ROOT / "results" / "skills_2.csv"
LOGS = ROOT / "logs"
RESULTS = ROOT / "results"

ZK_HOSTS = "127.0.0.1:2181,127.0.0.1:2182,127.0.0.1:2183"
SESSION_TIMEOUT_MS = 10_000

ELECTION = "/lab4/election"
CHECKPOINT = "/lab4/checkpoint"
POINTER = "/lab4/pointer"
EPOCH = "/lab4/epoch"

LOGS.mkdir(exist_ok=True)
RESULTS.mkdir(exist_ok=True)
