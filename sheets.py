"""구글시트 기록 (OAuth 사용자 인증).

원시데이터 탭: 빈방현황(전체) / Andaz Macau / Broadway Hotel
피벗 탭: {호텔명} {N}박  (날짜×룸타입 → 가능(N) or 불가)
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
    sh = gc.create(NEW_SHEET_TITLE)
    print("\n================ 새 구글시트 생성됨 ================")
    print(f"제목: {NEW_SHEET_TITLE}")
    print(f"GOOGLE_SHEET_ID={sh.id}")
    print(f"URL: https://docs.google.com/spreadsheets/d/{sh.id}/edit")
    print("→ 위 ID 를 .env 의 GOOGLE_SHEET_ID 에 넣으면 다음부터 이 시트에 적재됨")
    print("===================================================")
    return sh


def _worksheet(sh, title: str, cols: int):
    try:
        return sh.worksheet(title)
    except Exception:
        return sh.add_worksheet(title=title, rows=1, cols=cols)


def _overwrite(sh, title: str, header: list, rows: list[list]) -> None:
    """탭을 비우고 헤더 + 이번 측정값만 다시 쓴다 (누적 X)."""
    ws = _worksheet(sh, title, len(header))
    ws.clear()
    ws.append_rows([header] + rows, value_input_option="USER_ENTERED")


def _write_pivot(sh, tab_name: str, stay_rows: list,
                 hotel_name: str, nights: int, room_labels: list) -> None:
    """날짜×룸타입 피벗. 값: 가능(빈방수) 또는 불가."""
    rows = [r for r in stay_rows if r[1] == hotel_name and r[3] == nights]
    if not rows:
        return
    now = rows[0][0]
    date_map: dict[str, dict[str, str]] = {}
    for r in rows:
        date = r[2]
        label = r[4]
        units = r[9]
        status = r[10]
        if date not in date_map:
            date_map[date] = {}
        if status == "예약가능":
            date_map[date][label] = f"가능({units})"
        elif status == "누락":
            date_map[date][label] = "누락"
        else:
            date_map[date][label] = "불가"

    header = ["측정시각(KST)", "출발일"] + room_labels
    pivot_rows = [
        [now, date] + [date_map[date].get(rl, "불가") for rl in room_labels]
        for date in sorted(date_map)
    ]
    _overwrite(sh, tab_name, header, pivot_rows)


def append_rows(stay_rows: list[list]) -> None:
    """매 실행마다 시트를 덮어쓴다 (최신 1세트만 유지)."""
    gc = _client()
    sh = _open_spreadsheet(gc)

    # 1) 전체 원시데이터 탭
    _overwrite(sh, config.WS_STAY, config.SHEET_HEADER_RAW, stay_rows)

    # 2) 호텔별 원시데이터 탭 + 박수별 피벗 탭
    for hotel_info in config.HOTELS.values():
        name = hotel_info["name"]
        room_labels = list(hotel_info["room_types"].values())
        hotel_rows = [r for r in stay_rows if r[1] == name]

        # 원시데이터 탭
        _overwrite(sh, name, config.SHEET_HEADER_RAW, hotel_rows)

        # 박수별 피벗 탭 (예: "Broadway Hotel 3박", "Andaz Macau 4박")
        for nights in config.NIGHTS:
            _write_pivot(sh, f"{name} {nights}박", stay_rows, name, nights, room_labels)
