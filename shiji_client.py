from __future__ import annotations
"""Shiji CCM 접속 클라이언트.

로그인은 SPA 라서 Playwright(헤드리스 브라우저)로 처리하고,
실제 검색은 빠른 httpx 로 JSON API 를 직접 호출한다.
세션 쿠키는 state.json 에 저장해 재사용하고, 만료되면 자동 재로그인한다.
"""
import json
import os
import re
import time
from pathlib import Path

import httpx

import config

HERE = Path(__file__).parent
STATE_FILE = HERE / "state.json"          # 쿠키 저장
TOKEN_FILE = HERE / "hotel_token.txt"     # hotelIdFormHidden 캐시


class LoginRequired(Exception):
    pass


# ---------------------------------------------------------------- 로그인 (Playwright)
def login_with_browser(headless: bool = True) -> str:
    """브라우저로 로그인 → 쿠키를 state.json 에 저장, hotelIdFormHidden 토큰 반환."""
    from playwright.sync_api import sync_playwright

    user = os.environ["SHIJI_ID"]
    pw = os.environ["SHIJI_PW"]

    # 네트워크 요청에서 hotelIdFormHidden 토큰을 캡처하기 위한 저장소
    captured_token: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context()

        # 네트워크 요청/응답 인터셉트: hotelIdFormHidden 토큰 캡처
        def on_response(response):
            try:
                url = response.url
                # 주요 API 응답에서 토큰 탐색
                if any(k in url for k in [".do", "/api/", "/main", "/channel"]):
                    try:
                        body = response.text()
                        m = re.search(r"hotelIdFormHidden[\"']?\s*[:=]\s*[\"']?([a-f0-9]{32})", body)
                        if m and not captured_token:
                            captured_token.append(m.group(1))
                    except Exception:
                        pass
            except Exception:
                pass

        ctx.on("response", on_response)
        page = ctx.new_page()
        page.goto(config.BASE_URL + config.LOGIN_PATH, wait_until="networkidle")

        # SPA — 입력칸이 렌더될 때까지 대기 후 채운다.
        page.wait_for_selector("input", timeout=20000)
        _fill_login(page, user, pw)
        _submit_login(page)

        # 로그인 성공 = 메인으로 이동. URL 이 /auth 를 벗어날 때까지 대기.
        page.wait_for_url(lambda url: "/auth/login" not in url, timeout=30000)
        page.wait_for_load_state("networkidle")

        # 방법 1: HTML 에서 직접 추출
        token = _extract_token(page)

        # 방법 2: 네트워크 인터셉트로 캡처된 토큰 사용
        if not token and captured_token:
            token = captured_token[0]

        # 방법 3: 메인 페이지 직접 이동 후 재시도 (추가 대기 포함)
        if not token:
            token = _extract_token_with_navigation(page, captured_token)

        ctx.storage_state(path=str(STATE_FILE))
        browser.close()

    if not token:
        # 토큰 없이도 동작 가능한 경우를 위해 빈 문자열로 폴백
        # (일부 Shiji 환경에서는 hotelIdFormHidden 없이도 검색 가능)
        print("[경고] hotelIdFormHidden 토큰을 찾지 못했습니다. 빈 토큰으로 계속 진행합니다.", flush=True)
        token = ""
    TOKEN_FILE.write_text(token)
    return token


def _fill_login(page, user: str, pw: str) -> None:
    pw_box = page.query_selector("input[type=password]")
    if not pw_box:
        raise RuntimeError("비밀번호 입력칸을 못 찾음 (로그인 페이지 구조 변경?)")
    # 비번칸 앞쪽의 text/일반 input 을 아이디칸으로 사용
    inputs = page.query_selector_all("input")
    id_box = None
    for el in inputs:
        if el == pw_box:
            break
        t = (el.get_attribute("type") or "text").lower()
        if t in ("text", "email", "tel", ""):
            id_box = el
    if id_box is None:
        id_box = inputs[0]
    id_box.fill(user)
    pw_box.fill(pw)


def _submit_login(page) -> None:
    btn = (
        page.query_selector("button[type=submit]")
        or page.query_selector("button")
        or page.query_selector("input[type=submit]")
    )
    if btn:
        btn.click()
    else:
        page.keyboard.press("Enter")


def _extract_token(page) -> str | None:
    """현재 페이지 HTML에서 hotelIdFormHidden 토큰 추출 (다양한 패턴 시도)."""
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        html = page.content()
        # 패턴 1: hotelIdFormHidden=xxxxx (URL 파라미터 스타일)
        m = re.search(r"hotelIdFormHidden=([a-f0-9]{32})", html)
        if m:
            return m.group(1)
        # 패턴 2: hotelIdFormHidden": "xxxxx" (JSON 스타일)
        m = re.search(r'hotelIdFormHidden["\s]*[:=]["\s]*([a-f0-9]{32})', html)
        if m:
            return m.group(1)
        # 패턴 3: value="xxxxx" 근처에 hotelIdFormHidden
        m = re.search(r'name=["\']hotelIdFormHidden["\'][^>]*value=["\']([a-f0-9]{32})', html)
        if m:
            return m.group(1)
        m = re.search(r'value=["\']([a-f0-9]{32})["\'][^>]*name=["\']hotelIdFormHidden', html)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def _extract_token_with_navigation(page, captured_token: list) -> str | None:
    """메인 페이지로 이동하면서 토큰 재시도."""
    try:
        page.goto(config.BASE_URL + "/main.do", wait_until="networkidle", timeout=60000)
        time.sleep(3)
        for _ in range(5):
            try:
                token = _extract_token(page)
                if token:
                    return token
                if captured_token:
                    return captured_token[0]
            except Exception:
                pass
            time.sleep(2)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- httpx 세션
def _cookies_from_state() -> dict:
    if not STATE_FILE.exists():
        raise LoginRequired("저장된 세션 없음")
    state = json.loads(STATE_FILE.read_text())
    return {c["name"]: c["value"] for c in state.get("cookies", [])}


def build_client() -> httpx.Client:
    cookies = _cookies_from_state()
    return httpx.Client(
        base_url=config.BASE_URL,
        cookies=cookies,
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        },
        timeout=30.0,
        follow_redirects=False,
    )


def cached_token() -> str:
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    raise LoginRequired("저장된 토큰 없음")


# ---------------------------------------------------------------- 검색
def search(client: httpx.Client, token: str, hotel_code: str,
           arr: str, dep: str, adults: int, children: int) -> dict:
    """검색 1회 → 파싱된 결과 dict. (룸 수는 1실 고정 — 빈방수는 응답에서 직접 읽는다)

    반환: {
      "status": "SUCCESS"|...,
      "units": {roomTypeCode: int},                         # 빈방 수 (roomTypeList)
      "rates": {roomTypeCode: {ratePlanCode, amount, currency}},  # 룸타입별 최저가 (1박/1실 기준)
    }
    이 검색은 (arr~dep) 연박 전체가 빈 방인 룸타입만 돌려준다. amount 는 그 연박에
    적용되는 요금제(연박이면 LOS 프로모) 기준 '1박당' 요금이며 박수와 무관하게 일정하다
    (2/3/4박 동일값 검증 완료). 따라서 stay 총액 = amount × 박수.
    세션 만료 시 LoginRequired 발생.
    """
    body = {
        "wbeSearchCreteria.hotelCode": hotel_code,
        "wbeSearchCreteria.chainCode": config.CHAIN_CODE,
        "wbeSearchCreteria.ratePlanCode": "",
        "wbeSearchCreteria.arrDate": arr,
        "wbeSearchCreteria.depDate": dep,
        "wbeSearchCreteria.numberOfUnits": str(adults),
        "wbeSearchCreteria.numberOfChildren": str(children),
        "wbeSearchCreteria.numberOfRooms": "1",
        "crsno": "",
        "hotelIdFormHidden": token,
    }
    r = client.post(config.SEARCH_PATH, data=body)
    if r.status_code in (301, 302) or "/auth/login" in str(r.headers.get("location", "")):
        raise LoginRequired("검색 요청이 로그인으로 리다이렉트됨")
    try:
        j = r.json()
    except Exception:
        raise LoginRequired("응답이 JSON 이 아님 (세션 만료 추정)")

    units: dict[str, int] = {}
    for x in (j.get("roomTypeList") or []):
        c = x.get("roomTypeCode")
        n = x.get("numberOfUnits")
        if c and n not in (None, ""):
            units[c] = int(n)

    # 룸타입별로 여러 요금제가 올 수 있다 → 최저가 + 그 코드만 채택
    rates: dict[str, dict] = {}
    for item in (j.get("roomRateList") or []):
        code = item.get("roomTypeCode")
        base = (item.get("baseList") or [{}])[0]
        amt = base.get("amount")
        if code is None or amt in (None, ""):
            continue
        amt = float(amt)
        cur = base.get("currencyCode") or config.CURRENCY
        if code not in rates or amt < rates[code]["amount"]:
            rates[code] = {"ratePlanCode": item.get("ratePlanCode"),
                           "amount": amt, "currency": cur}
    return {"status": j.get("resultStatusFlag"), "units": units, "rates": rates}


def ensure_session() -> tuple[httpx.Client, str]:
    """유효한 (client, token) 확보. 없거나 만료면 자동 로그인."""
    try:
        client = build_client()
        token = cached_token()
        # 가벼운 검증 검색
        probe_hotel = next(iter(config.HOTELS))
        search(client, token, probe_hotel,
               config.ARR_START.isoformat(),
               _plus_days(config.ARR_START, 3),
               int(os.environ.get("ADULTS", 2)),
               int(os.environ.get("CHILDREN", 0)))
        return client, token
    except LoginRequired:
        token = login_with_browser(headless=True)
        return build_client(), token


def _plus_days(d, n: int) -> str:
    from datetime import timedelta
    return (d + timedelta(days=n)).isoformat()
