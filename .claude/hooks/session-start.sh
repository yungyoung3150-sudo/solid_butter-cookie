#!/bin/bash
# Claude Code on the web — SessionStart 셋업 훅
# 맥북/아이패드 등 어느 기기에서 세션을 시작하든 동일한 환경이 갖춰지도록
# 클라우드 컨테이너에 의존성을 설치한다. (기기 간 작업 연속성 보장)
set -euo pipefail

# 로컬 터미널 세션에는 영향 주지 않고, 클라우드(web) 세션에서만 실행
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

echo "[session-start] Python 의존성 설치 중..."
pip install --quiet --disable-pip-version-check -r requirements.txt

echo "[session-start] Playwright Chromium 설치 중..."
# 크롤러 로그인은 Chromium 이 필요하다. 네트워크 정책으로 다운로드가 막혀도
# 코드 편집 자체는 가능하므로 세션 자체를 실패시키지 않고 경고만 남긴다.
if ! python -m playwright install --with-deps chromium; then
  echo "[session-start] WARN: Chromium 설치 실패 (네트워크 정책 가능성). 크롤/로그인 실행은 제한될 수 있으나 코드 작업은 영향 없음."
fi

# 출력 디렉터리(.gitignore 대상이라 새 클론에는 없음)
mkdir -p data

# .env 가 없으면 예시에서 생성 → load_dotenv 가 깨지지 않게
if [ ! -f .env ]; then
  cp .env.example .env
  echo "[session-start] .env 를 .env.example 에서 생성함 (실제 실행 전 값 채우기)."
fi

echo "[session-start] 셋업 완료."
