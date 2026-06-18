# 맥북 ↔ 아이패드 작업 연속성 (Claude Code on the web)

회사에서 맥북으로 시작한 작업을 집/주말에 아이패드로 이어서 하기 위한 설정.
핵심 아이디어: **작업은 기기가 아니라 Anthropic 클라우드 컨테이너에서 돌아간다.**
기기는 같은 claude.ai 계정으로 접속하는 "창문"일 뿐이라 세션·브랜치가 그대로 이어진다.

## 자동 환경 셋업 (SessionStart 훅)

`.claude/hooks/session-start.sh` 가 **클라우드 세션이 시작될 때마다 자동 실행**된다.
(`.claude/settings.json` 의 `SessionStart` 훅으로 등록됨)

훅이 하는 일:
1. `pip install -r requirements.txt`
2. `playwright install chromium` (브라우저 로그인용 — 아래 네트워크 주의 참고)
3. `data/` 디렉터리 생성 (출력용, .gitignore 대상이라 새 클론엔 없음)
4. `.env` 가 없으면 `.env.example` 에서 생성

덕분에 맥북에서 열든 아이패드에서 열든 **매번 동일한 환경**이 보장된다.
로컬 터미널 세션에는 영향이 없도록 `CLAUDE_CODE_REMOTE=true` 일 때만 동작한다.

> 훅은 동기(synchronous) 모드라, 셋업이 끝난 뒤 세션이 시작된다.
> 시작 속도를 더 원하면 스크립트 첫 줄에서 async 모드로 전환 가능.

## ⚠️ Chromium 다운로드 네트워크 허용 필요

크롤러 로그인은 Playwright Chromium 이 필요한데, 다운로드 호스트
`playwright.azureedge.net` (및 미러)가 **기본 네트워크 정책에서 차단**된다.
훅은 이 경우 세션을 실패시키지 않고 경고만 남기고 진행한다(코드 편집은 무관).

클라우드 세션에서 **크롤러를 실제로 실행**까지 하려면, 환경의
네트워크 egress 설정(claude.ai/code 웹의 Environment 설정)에 아래 호스트를 추가:

- `playwright.azureedge.net`
- `playwright-akamai.azureedge.net`
- `playwright-verizon.azureedge.net`

> 단순히 코드를 수정/리뷰/PR 하는 연속성에는 위 설정이 필요 없다.
> 어차피 실제 정기 수집은 GitHub Actions(`.github/workflows/crawl.yml`)가 돌린다.

## 권장 워크플로우

1. **맥북(회사)**: claude.ai/code 웹 또는 터미널 `claude --remote "..."` 로 작업 시작.
   - 로컬 커밋이 있으면 **푸시 후** 자리 비우기 (클라우드는 GitHub 에서 클론함).
2. **이동/퇴근**: 그냥 닫으면 됨. 클라우드에서 계속 진행됨.
3. **아이패드(집)**: Claude 모바일 앱 또는 사파리로 claude.ai/code 접속 →
   같은 세션이 그대로 보임. 진행 확인·추가 지시·검토·PR 까지 가능.

### 터미널과 엮을 때 (참고)
- 터미널 → 웹: `claude --remote "..."` (새 클라우드 세션 생성)
- 웹 → 터미널: `claude --teleport` (클라우드 세션+브랜치를 로컬로 가져옴)
- 진행 중인 로컬 터미널 세션을 그대로 웹으로 올리는 건 CLI 로는 불가
  (맥북 데스크톱 앱의 "Continue in" 메뉴로는 가능).

## 전제
- 두 기기 모두 **같은 claude.ai 계정** 로그인.
- Claude Code on the web 은 Pro/Max/Team(및 일부 Enterprise) 대상.
- 이 훅은 **기본 브랜치(main)에 머지된 뒤**부터 모든 새 클라우드 세션에 적용된다.
