"""로그인 + 단일 검색 스모크 테스트. 빠른 상태 점검용."""
import os
from dotenv import load_dotenv

load_dotenv()

from shiji_client import ensure_session, search

client, token = ensure_session()
print("세션 OK. 토큰 길이:", len(token))

res = search(client, token, "BMHMO", "2026-07-01", "2026-07-04",
             int(os.environ.get("ADULTS", 2)), int(os.environ.get("CHILDREN", 0)))
print("status:", res["status"])
print("빈방수(units):", res["units"])
print("최저가(rates):", res["rates"])
client.close()
