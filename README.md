# Shiji 숙박 빈방·가격 크롤러

Shiji CCM 콘솔(`ccm-console.shijicloud.com`)의 New Booking 검색을 자동화해서,
호텔별 룸타입 최저가와 빈방 여부를 주기적으로 구글시트에 적재한다.

## 수집 규칙 (config.py 에서 수정)
- **호텔:** Andaz Macau(ADZMO), Broadway Hotel(BMHMO)
- **arrival 범위:** 2026-07-01 ~ 2026-08-01
- **박수:** 3박, 4박 (각 arrival 마다 둘 다)
- **룸타입:** ADZMO 4종(킹/트윈/킹고층/트윈고층), BMHMO 4종(시티뷰·리버뷰 × 킹·트윈)
- **수집값:** 룸타입별 **빈방수 + 최저가 + 그 최저가의 요금코드**

> **빈방수**: 검색 응답의 `roomTypeList[].numberOfUnits` 를 그대로 읽는다 (정확한 잔여 객실 수).
> **1박가(첫날)**: Shiji 가 stay 총액을 안 주고 *첫날 1박 1실* 야간가만 준다. 그 값을 그대로 기록.
> 같은 룸타입에 요금제가 여러 개면 그 중 **최저가 + 코드**만 남긴다.
> **상태**: `예약가능`(요금 있음) / `요금없음`(방은 있으나 예약 불가) / `빈방없음`(잔여 0).

## 동작 방식
- 로그인은 SPA 라서 **Playwright** 로 처리 → 쿠키를 `state.json` 에 저장해 재사용.
- 실제 검색은 빠른 **httpx** 로 JSON API(`channelBookIng_bookSearch.do`)를 직접 호출.
- 세션이 만료되면 자동으로 다시 로그인한다.

## 설치
```bash
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env   # 값 채우기
```

## 실행
```bash
python run_once.py     # 1회 수집
python scheduler.py    # KST 08~20시 매시 정각 자동 수집
```

## 환경변수(.env)
| 키 | 설명 |
|----|------|
| `SHIJI_ID` / `SHIJI_PW` | CCM 로그인 (브라우저 로그인에만 사용) |
| `ADULTS` / `CHILDREN` | 검색 인원 (기본 2/0) |
| `GOOGLE_SHEET_ID` | 적재할 구글시트 ID |
| `GOOGLE_CREDENTIALS` | 서비스계정 JSON 파일명 |
| `SINK` | `sheet`(기본) 또는 `local`(CSV만) |

## 출력 (구글시트 탭 2개 + 로컬 CSV 2개)
- **날짜별단가** (`data/calendar.csv`): 측정시각·호텔·날짜·룸타입·1박단가·요금코드·통화·빈방수·상태
  - Shiji 가 주는 '그 날짜 1박' 야간가. arrival 전 날짜를 다 돌아 캘린더로 복원 (2박 윈도우 역산과 일치 검증 완료).
- **stay총액** (`data/stay.csv`): 측정시각·호텔·숙박시작일·박수·룸타입·총액·평균1박가·통화·빈방수·상태
  - 총액 = 날짜별단가를 박수만큼 합산 → 날짜마다 다른 가격이 그대로 반영됨.
- 상태: `예약가능` / `요금없음`(방은 있으나 요금 닫힘) / `빈방없음` / `예약가능(총액미상)`(일부 박 단가 누락).
