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


def _pivot(stay_rows: list, hotel_code: str, nights: int, room_labels: list) -> tuple:
    """날짜×룸타입 피벗.
    반환: (header, data_rows)
    header: [측정시각(KST), 출발일, 룸타입1, 룸타입2, ...]
    data_rows: 날짜 1행에 룸타입별 '가능(N)' 또는 '불가' 값
    """
    from collections import defaultdict
    # {(측정시각, 출발일): {룸타입: (units, status)}}
    table: dict = defaultdict(dict)
    for r in stay_rows:
        if r[1] != hotel_code or r[3] != nights:
            continue
        ts, date, label, units, status = r[0], r[2], r[4], r[5], r[6]
        table[(ts, date)][label] = (units, status)

    header = ["측정시각(KST)", "출발일"] + room_labels
    rows = []
    for (ts, date) in sorted(table.keys(), key=lambda x: x[1]):
        row = [ts, date]
        for label in room_labels:
            info = table[(ts, date)].get(label)
            if info is None:
                row.append("누락")
            else:
                units, status = info
                if status == "예약가능":
                    row.append(f"가능({units})")
                elif status == "누락":
                    row.append("누락")
                else:
                    row.append("불가")
        rows.append(row)
    return header, rows


def _apply_red_formatting(sh, ws, num_room_cols: int) -> None:
    """'불가' 셀만 빨간색 조건부 서식. 측정시각·출발일 열 제외."""
    import gspread
    sheet_id = ws.id
    spreadsheet = sh.fetch_sheet_metadata()
    for s in spreadsheet['sheets']:
        if s['properties']['sheetId'] == sheet_id:
            existing = s.get('conditionalFormats', [])
            break
    else:
        existing = []

    delete_reqs = [
        {"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": 0}}
        for _ in existing
    ]
    if delete_reqs:
        sh.batch_update({"requests": delete_reqs})

    RED = {"red": 1.0, "green": 0.7, "blue": 0.7}
    requests = []
    for col_idx in range(2, 2 + num_room_cols):  # C열부터 룸타입 열까지
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "startColumnIndex": col_idx,
                        "endColumnIndex": col_idx + 1,
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "TEXT_EQ",
                            "values": [{"userEnteredValue": "불가"}]
                        },
                        "format": {"backgroundColor": RED}
                    }
                },
                "index": 0
            }
        })
    if requests:
        sh.batch_update({"requests": requests})


def append_rows(stay_rows: list[list]) -> None:
    """4개 탭에 피벗 형식으로 기록: Broadway/Andaz × 2박3일/3박4일.
    내부 row 형식: [측정시각, hotel_code, 출발일, nights, 룸타입, 예약가능객실수, 상태]
    시트 형식: 날짜 1행 × 룸타입 열 (가능(N) / 불가)
    """
    gc = _client()

    # GOOGLE_SHEET_ID 에 콤마로 여러 시트 ID 를 주면 그 전부에 동일 기록한다(예: Shiji + 갤럭시).
    ids = [s.strip() for s in os.environ.get("GOOGLE_SHEET_ID", "").split(",") if s.strip()]
    sheets_to_write = [gc.open_by_key(sid) for sid in ids] if ids else [_open_spreadsheet(gc)]

    for sh in sheets_to_write:
        for (hotel_code, nights), tab_name in config.WS_TABS.items():
            room_labels = list(config.HOTELS[hotel_code]["room_types"].values())
            header, rows = _pivot(stay_rows, hotel_code, nights, room_labels)
            _overwrite(sh, tab_name, header, rows)
            ws = sh.worksheet(tab_name)
            _apply_red_formatting(sh, ws, len(room_labels))
            print(f"  [{sh.title}/{tab_name}] {len(rows)}행", flush=True)
