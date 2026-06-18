"""로컬 CSV 저장 (시트와 별개로 항상 백업). stay 1개 파일.

매 실행마다 '덮어쓴다' (최신 1세트만 유지 — 시트와 동일 정책)."""
import csv
from pathlib import Path

import config

DATA_DIR = Path(__file__).parent / "data"
STAY_FILE = DATA_DIR / "stay.csv"


def append(stay_rows: list[list]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with STAY_FILE.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(config.SHEET_HEADER_RAW)
        w.writerows(stay_rows)
