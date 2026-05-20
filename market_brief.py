import os
import sys
import json
import smtplib
import requests
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic

KST = timezone(timedelta(hours=9))


def get_date() -> str:
    return datetime.now(KST).strftime("%Y년 %m월 %d일")


def generate_reports(client: anthropic.Anthropic, date_str: str) -> tuple[str, str]:
    prompt = f"""당신은 미국 주식시장 전문 애널리스트입니다. 오늘({date_str}) 마감된 미국 증시를 웹에서 검색하여 두 가지 리포트를 한국어로 작성하세요.

Reuters, Bloomberg, CNBC, MarketWatch, Yahoo Finance, 네이버 금융, 한국경제, 이데일리에서 오늘자 최신 데이터를 검색하세요.
실제 수치(지수값, 등락률, 종목명 등)를 반드시 포함하세요.

===EMAIL_REPORT===
[미국증시 브리핑] {date_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 1. 미국 3대 지수
• S&P 500:  (지수값) (등락폭) (등락률%)
• 나스닥:    (지수값) (등락폭) (등락률%)
• 다우존스:  (지수값) (등락폭) (등락률%)
→ (핵심 원인 2~3줄)

📈 2. 섹터별 수급 흐름
▲ 강세 TOP 3:
  1. (섹터명): +(등락률)% — (이유)
  2. (섹터명): +(등락률)% — (이유)
  3. (섹터명): +(등락률)% — (이유)
▼ 약세 TOP 3:
  1. (섹터명): -(등락률)% — (이유)
  2. (섹터명): -(등락률)% — (이유)
  3. (섹터명): -(등락률)% — (이유)

🚀 3. 주도주 TOP 5
1. (종목명) ((티커)): (등락률)%, 거래량 (배수)배 — (이유)
2. (종목명) ((티커)): (등락률)%, 거래량 (배수)배 — (이유)
3. (종목명) ((티커)): (등락률)%, 거래량 (배수)배 — (이유)
4. (종목명) ((티커)): (등락률)%, 거래량 (배수)배 — (이유)
5. (종목명) ((티커)): (등락률)%, 거래량 (배수)배 — (이유)

📰 4. 주요 이슈
• (연준 발언 / 경제지표 / 어닝 서프라이즈 등 핵심 이슈 3~5개)

🇰🇷 5. 한국 증시 영향 분석
• 예상 방향: (코스피/코스닥 예상 방향)
• 주목 섹터: (영향받을 국내 섹터 및 종목)
• 리스크: (주의할 점)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
===KAKAO_SUMMARY===
(아래 형식으로 350자 이내 작성)
S&P500 (등락률)% | 나스닥 (등락률)% | 다우 (등락률)%

▲강세: (섹터1), (섹터2), (섹터3)
▼약세: (섹터1), (섹터2), (섹터3)

💡(핵심 이슈 1~2줄)

🇰🇷한국: (예상 방향 + 주목 섹터)

📧 상세보고서는 이메일 확인"""

    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20250305", "name": "web_search"}]
    full_text = ""

    for _ in range(20):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            tools=tools,
            messages=messages,
        )

        for block in response.content:
            if getattr(block, "type", None) == "text":
                full_text += block.text

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = [
                {"type": "tool_result", "tool_use_id": b.id, "content": ""}
                for b in response.content
                if getattr(b, "type", None) == "tool_use"
            ]
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
        else:
            break

    email_report = full_text.strip()
    kakao_summary = ""

    if "===EMAIL_REPORT===" in full_text and "===KAKAO_SUMMARY===" in full_text:
        after_marker = full_text.split("===EMAIL_REPORT===", 1)[1]
        parts = after_marker.split("===KAKAO_SUMMARY===", 1)
        email_report = parts[0].strip()
        if len(parts) > 1:
            kakao_summary = parts[1].strip()[:380]
    else:
        kakao_summary = full_text[:180].strip() + "\n\n📧 상세보고서는 이메일 확인"

    return email_report, kakao_summary


def get_kakao_token() -> str | None:
    refresh = os.environ.get("KAKAO_REFRESH_TOKEN")
    client_id = os.environ.get("KAKAO_CLIENT_ID")

    if refresh and client_id:
        data = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh,
        }
        secret = os.environ.get("KAKAO_CLIENT_SECRET")
        if secret:
            data["client_secret"] = secret

        r = requests.post("https://kauth.kakao.com/oauth/token", data=data, timeout=10)
        if r.status_code == 200:
            return r.json().get("access_token")
        print(f"KakaoTalk token refresh failed: {r.text}")

    return os.environ.get("KAKAO_ACCESS_TOKEN")


def send_kakao(title: str, summary: str) -> bool:
    token = get_kakao_token()
    if not token:
        print("KakaoTalk: No token — skipped")
        return False

    template = {
        "object_type": "feed",
        "content": {
            "title": title[:100],
            "description": summary[:380],
            "link": {
                "web_url": "https://finance.yahoo.com",
                "mobile_web_url": "https://finance.yahoo.com",
            },
        },
    }

    r = requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"template_object": json.dumps(template, ensure_ascii=False)},
        timeout=10,
    )

    if r.status_code == 200 and r.json().get("result_code") == 0:
        print("KakaoTalk: Sent")
        return True

    print(f"KakaoTalk: Failed {r.status_code} — {r.text}")
    return False


def send_email(subject: str, body: str) -> bool:
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD")
    recipient = os.environ.get("EMAIL_RECIPIENT", "sangnom12@gmail.com")

    if not sender or not password:
        print("Email: No credentials — skipped")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    html = (
        "<html><body>"
        "<pre style='font-family:\"Malgun Gothic\",\"Apple SD Gothic Neo\",Arial,sans-serif;"
        "font-size:14px;line-height:1.8;white-space:pre-wrap'>"
        f"{body}"
        "</pre></body></html>"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(sender, password)
            s.sendmail(sender, recipient, msg.as_string())
        print(f"Email: Sent → {recipient}")
        return True
    except Exception as e:
        print(f"Email: Failed — {e}")
        return False


def main() -> None:
    date_str = get_date()
    subject = f"[미국증시 브리핑] {date_str}"

    print(f"Generating report for {date_str}…")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    email_report, kakao_summary = generate_reports(client, date_str)

    if not email_report:
        print("Empty report — aborting")
        sys.exit(1)

    print(f"Report: {len(email_report)} chars | KakaoTalk: {len(kakao_summary)} chars")

    kakao_ok = send_kakao(subject, kakao_summary)
    email_ok = send_email(subject, email_report)

    if not kakao_ok and not email_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
