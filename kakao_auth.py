"""
카카오톡 나에게 보내기 — 초기 토큰 발급 스크립트
한 번만 실행하면 GitHub Secrets에 등록할 토큰을 얻을 수 있습니다.

사전 준비:
  pip install requests
  https://developers.kakao.com 에서 앱 생성 후
  → 제품 > 카카오 로그인 활성화
  → 동의항목 > 카카오톡 메시지 전송 추가
  → 앱 설정 > Redirect URI → http://localhost:5000/callback 추가

실행:
  python kakao_auth.py
"""
import json
import webbrowser
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

REDIRECT_URI = "http://localhost:5000/callback"
_code: list[str] = []


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            _code.append(params["code"][0])
            self.send_response(200)
            self.end_headers()
            self.wfile.write("✅ 인증 완료! 이 창을 닫으세요.".encode("utf-8"))
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Authorization failed.")

    def log_message(self, *_):
        pass


def main():
    client_id = input("Kakao REST API 키: ").strip()
    client_secret = input("Client Secret (없으면 Enter): ").strip()

    auth_url = "https://kauth.kakao.com/oauth/authorize?" + urlencode(
        {
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "talk_message",
        }
    )

    print("\n브라우저에서 카카오 로그인 후 인증을 완료하세요…")
    webbrowser.open(auth_url)
    HTTPServer(("localhost", 5000), _Handler).handle_request()

    if not _code:
        print("인증 코드를 받지 못했습니다.")
        return

    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "code": _code[0],
    }
    if client_secret:
        data["client_secret"] = client_secret

    r = requests.post("https://kauth.kakao.com/oauth/token", data=data, timeout=10)
    if r.status_code != 200:
        print(f"토큰 발급 실패: {r.text}")
        return

    tokens = r.json()
    print("\n✅ 토큰 발급 성공! GitHub Secrets에 아래 값을 추가하세요:\n")
    print(f"  KAKAO_CLIENT_ID:     {client_id}")
    if client_secret:
        print(f"  KAKAO_CLIENT_SECRET: {client_secret}")
    print(f"  KAKAO_ACCESS_TOKEN:  {tokens.get('access_token')}")
    print(f"  KAKAO_REFRESH_TOKEN: {tokens.get('refresh_token')}")

    with open("kakao_tokens.json", "w", encoding="utf-8") as f:
        json.dump({"client_id": client_id, **tokens}, f, indent=2, ensure_ascii=False)
    print("\n⚠️  kakao_tokens.json 파일은 .gitignore에 있으니 절대 커밋하지 마세요!")


if __name__ == "__main__":
    main()
