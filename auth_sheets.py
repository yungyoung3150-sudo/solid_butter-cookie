"""1회용: 구글 OAuth 동의로 시트 접근 토큰을 받아 token_sheets.json 에 저장.

실행하면 브라우저가 열린다. koo@yestravel.co.kr 로 로그인하고
'스프레드시트 + 본인이 만든 파일' 권한을 허용하면 토큰이 저장된다.
이후 크롤러는 이 토큰으로 자동 동작한다(브라우저 재동의 불필요).
"""
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

HERE = Path(__file__).parent
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


def main():
    flow = InstalledAppFlow.from_client_secrets_file(
        str(HERE / "client_secret.json"), scopes=SCOPES)
    creds = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
        authorization_prompt_message="브라우저에서 동의 화면을 여는 중... ({url})",
        success_message="완료! 이 탭은 닫아도 됩니다. 터미널을 확인하세요.",
    )
    (HERE / "token_sheets.json").write_text(creds.to_json())
    print("\n토큰 저장 완료 → token_sheets.json")


if __name__ == "__main__":
    main()
