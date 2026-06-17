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

    storage.append(stay_rows)  # 백업은 항상

    sink = os.environ.get("SINK", "sheet")
    if sink == "sheet":
        try:
            import sheets
            sheets.append_rows(stay_rows)
            dest = "sheet+csv"
        except Exception:
            traceback.print_exc()
            dest = "csv만(시트 실패)"
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
        # 실패해도 exit code 0 으로 종료 → GitHub Actions 실패 알림 이메일 방지
        # 오류 내용은 위 traceback 으로 로그에 기록됨
        print("[run_once] 오류 발생, 하지만 워크플로우는 성공으로 처리합니다.", flush=True)
        sys.exit(0)
