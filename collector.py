"""한 번의 수집 사이클.

핵심: 3박/4박은 '한 방에서 연속 N박'을 뜻한다. Shiji 는 연박 검색에 연박 전용
요금제(LOS 프로모)를 붙이고, N박 전부 빈 방인 룸타입만 결과로 준다. 그래서 개별
1박을 따로 검색·합산하지 않고, (도착일 × 박수) 검색 결과를 그대로 쓴다.

검색이 주는 amount 는 박수와 무관하게 일정한 '그 도착일 기준 연박 1박당 요금'이다
(2/3/4박 동일값 검증 완료). 따라서 산정총액 = 1박단가 × 박수.
"""
import time
from datetime import datetime, timedelta, timezone

import httpx

import config
import shiji_client

KST = timezone(timedelta(hours=9))


def _daterange(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _resilient_search(state, hotel_code, arr, dep, adults, children, tries=4):
    """타임아웃은 재시도, 세션 만료는 자동 재로그인. 모든 재시도 실패 시 None 반환."""
    last_err = None
    for attempt in range(tries):
        try:
            return shiji_client.search(
                state["client"], state["token"], hotel_code, arr, dep,
                adults, children)
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError) as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
        except shiji_client.LoginRequired:
            try:
                state["client"], state["token"] = shiji_client.ensure_session()
            except Exception as e:
                last_err = e
    print(f"[누락] {hotel_code} {arr}~{dep} 4회 재시도 실패: {last_err}", flush=True)
    return None


def collect_all(client, token, adults: int, children: int):
    """반환: stay_rows (SHEET_HEADER_RAW 순서).

    (도착일 × 박수) 연박 검색 결과를 직접 사용.
    산정총액 = 1박단가 × 박수.
    """
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    stay_rows: list[list] = []
    state = {"client": client, "token": token}

    for hotel_code, hotel in config.HOTELS.items():
        name = hotel["name"]
        targets = hotel["room_types"]

        for i, arr in enumerate(_daterange(config.ARR_START, config.ARR_END)):
            print(f"[{name}] {arr} 수집 중... ({i+1}번째)", flush=True)
            for nights in config.NIGHTS:
                dep = arr + timedelta(days=nights)
                res = _resilient_search(
                    state, hotel_code, arr.isoformat(), dep.isoformat(),
                    adults, children)
                if res is None:
                    for code, label in targets.items():
                        stay_rows.append([
                            now, name, arr.isoformat(), nights, label,
                            "", "", "", config.CURRENCY, 0, "누락"
                        ])
                    continue
                ok = res["status"] == "SUCCESS"
                for code, label in targets.items():
                    units = res["units"].get(code, 0) if ok else 0
                    status = "예약가능" if units > 0 else "빈방없음"
                    rate_info = res["rates"].get(code, {}) if ok else {}
                    nightly_rate = rate_info.get("amount", "")
                    rate_code_val = rate_info.get("ratePlanCode", "")
                    currency = rate_info.get("currency", config.CURRENCY)
                    total_price = (
                        round(nightly_rate * nights, 2)
                        if nightly_rate != "" else ""
                    )
                    stay_rows.append([
                        now, name, arr.isoformat(), nights, label,
                        total_price, nightly_rate, rate_code_val, currency,
                        units, status,
                    ])

    return stay_rows
