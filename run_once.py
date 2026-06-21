"""수집 1회 실행. cron/스케줄러가 이걸 호출한다. 단독 실행도 가능."""
import os
import sys
import time
import traceback

from dotenv import load_dotenv

load_dotenv()

import collector
import storage
from shiji_client import ensure_session


def run_once() -> int:
    t0 = time.time()
    adults = int(os.environ.get("ADULTS", 2))
    children = int(os.environ.get("CHILDREN", 0))

    client, token = ensure_session()
    try:
        stay_rows = collector.collect_all(client, token, adults, children)
    finally:
        client.close()

    storage.append(stay_rows)  # 백업은 항상(시트 기록 성패와 무관)

    # ── 신뢰 가드 ──────────────────────────────────────────────
    # 목적: '신선해 보이지만 틀린' 시트를 만들지 않는다. 크롤이 건전할 때만 시트에 쓴다.
    # 누락 = 검색이 4회 재시도 후에도 실패한 건(=세션/로그인/네트워크 문제). 정상 런은 거의 0.
    total = len(stay_rows)
    missing = sum(1 for r in stay_rows if r[-1] == "누락")
    if total == 0:
        raise RuntimeError("수집 결과 0행 — 크롤 비정상. 시트 미기록.")
    if missing > total * 0.5:
        raise RuntimeError(
            f"누락 과다 {missing}/{total}(>50%) — 로그인/세션 의심. "
            "신뢰 불가 데이터라 시트에 쓰지 않고 런을 실패시킴.")

    sink = os.environ.get("SINK", "sheet")
    if sink == "sheet":
        # 시트 기록 실패는 삼키지 않는다 → 런이 빨갛게 실패 = GitHub 자동 실패메일.
        # (조용한 시트 동결 = '6:25 재발'을 못 보는 사태 방지)
        import sheets
        sheets.append_rows(stay_rows)
        dest = "sheet+csv"
    else:
        dest = "csv"

    ok = sum(1 for r in stay_rows if r[-1] == "예약가능")
    print(f"[run_once] stay {len(stay_rows)}행 "
          f"(예약가능 {ok}) -> {dest}  {time.time()-t0:.1f}s")
    return len(stay_rows)


if __name__ == "__main__":
    try:
        run_once()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
