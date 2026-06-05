"""수집 대상/규칙 정의. 동작을 바꾸려면 대부분 이 파일만 수정하면 된다."""
from datetime import date

BASE_URL = "https://ccm-console.shijicloud.com"
SEARCH_PATH = "/channelBookIng_bookSearch.do"
LOGIN_PATH = "/auth/login"
CHAIN_CODE = "CCM"
CURRENCY = "MOP"

# arrival date 수집 범위 (양 끝 포함)
ARR_START = date(2026, 7, 1)
ARR_END = date(2026, 8, 1)

# 숙박일 수 (각 arrival 마다 모두 수집)
NIGHTS = [3, 4]

# 수집 대상 호텔 + 룸타입(코드 -> 사람이 읽는 라벨)
# roomTypeCode 는 응답 roomRateList[].roomTypeCode 와 매칭된다.
HOTELS = {
    "ADZMO": {
        "name": "Andaz Macau",
        "room_types": {
            "KING": "킹베드",
            "TWIN": "트윈베드",
            "HFLK": "킹베드 고층",
            "HFLT": "트윈베드 고층",
        },
    },
    "BMHMO": {
        "name": "Broadway Hotel",
        "room_types": {
            "BGK": "시티뷰 킹베드",
            "BGT": "시티뷰 트윈베드",
            "BRK": "리버뷰 킹베드",
            "BRT": "리버뷰 트윈베드",
        },
    },
}

# stay총액: 도착일×박수 연박 검색을 직접 사용. 산정총액 = 1박단가 × 박수
SHEET_HEADER_STAY = [
    "측정시각(KST)",
    "호텔",
    "숙박시작일",
    "박수",
    "룸타입",
    "산정총액",
    "1박단가",
    "요금코드",
    "통화",
    "빈방수",
    "상태",
]

# 구글시트 워크시트(탭) 이름
WS_STAY = "stay총액"
