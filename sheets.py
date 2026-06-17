"""구글시트 기록 (OAuth 사용자 인증 — 쿠 본인 계정). 탭 1개: stay총액.

서비스계정/공유 불필요. token_sheets.json (auth_sheets.py 로 1회 발급) 을 쓴다.
GOOGLE_SHEET_ID 가 비어 있으면 본인 드라이브에 새 시트를 만들고 ID 를 출력한다.
"""
import os
from pathlib import Path

import config

HERE = Path(__file__).parent
TOKEN_FILE = HERE / "token_sheets.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]
NEW_SHEET_TITLE = "Shiji 빈방현황"


def _client():
    import gspread
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    if not TOKEN_FILE.exists():
        raise RuntimeError("token_sheets.json 없음 → 먼저 `python auth_sheets.py` 실행")
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())
    return gspread.authorize(creds)


def _open_spreadsheet(gc):
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "").strip()
    if sheet_id:
        return gc.open_by_key(sheet_id)
    # ID 미설정 → 새로 만들고 안내
    sh = gc.create(NEW_SHEET_TITLE)
    print("\n================ 새 구글시트 생성됨 ================")
    print(f"제목: {NEW_SHEET_TITLE}")
    print(f"GOOGLE_SHEET_ID={sh.id}")
    print(f"URL: https://docs.google.com/spreadsheets/d/{sh.id}/edit")
    print("→ 위 ID 를 .env 의 GOOGLE_SHEET_ID 에 넣으면 다음부터 이 시트에 적재됨")
    print("===================================================")
    return sh


def _worksheet(sh, title: str, header: list):
    try:
        return sh.worksheet(title)
    except Exception:
        return sh.add_worksheet(title=title, rows=1, cols=len(header))


def _overwrite(sh, title: str, header: list, rows: list[list]) -> None:
    """탭을 비우고 헤더 + 이번 측정값만 다시 쓴다 (누적 X)."""
    ws = _worksheet(sh, title, header)
    ws.clear()
    ws.append_rows([header] + rows, value_input_option="USER_ENTERED")


def append_rows(stay_rows: list[list]) -> None:
    """이름은 append 지만 매 실행마다 시트를 '덮어쓴다' (최신 1세트만 유지).
    전체(stay총액) + 호텔별 탭(Andaz Macau / Broadway Hotel) 동시 기록."""
    gc = _client()
    sh = _open_spreadsheet(gc)

    # 1) 전체 탭
    _overwrite(sh, config.WS_STAY, config.SHEET_HEADER_STAY, stay_rows)

    # 2) 호텔별 탭
    import config as _cfg
    for hotel_info in _cfg.HOTELS.values():
        name = hotel_info["name"]
        hotel_rows = [r for r in stay_rows if r[1] == name]
        _overwrite(sh, name, _cfg.SHEET_HEADER_STAY, hotel_rows)
