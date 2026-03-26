"""텔레그램 프리뷰 알림 모듈."""

import httpx
from config import TELEGRAM_BOT_TOKEN as BOT_TOKEN, TELEGRAM_CHAT_ID as CHAT_ID

TELEGRAM_API = "https://api.telegram.org"


def send_preview(content):
    """생성된 포스트 프리뷰를 텔레그램으로 전송."""
    if not BOT_TOKEN or not CHAT_ID:
        print("[텔레그램] BOT_TOKEN 또는 CHAT_ID 미설정, 알림 건너뜀")
        return False
    return _send_message(_format_text_preview(content))


def send_result(result):
    """포스팅 완료 결과를 텔레그램으로 전송."""
    if not BOT_TOKEN or not CHAT_ID:
        return False

    lines = ["[AI Threads 포스팅 완료]"]
    if result.get("post_id"):
        lines.append(f"메인: {result['post_id']}")
    if result.get("analysis_id"):
        lines.append(f"분석: {result['analysis_id']}")
    if result.get("reply_id"):
        lines.append(f"첫 댓글: {result['reply_id']}")
    if result.get("link_id"):
        lines.append(f"링크: {result['link_id']}")

    return _send_message("\n".join(lines))


def _format_text_preview(content):
    """텍스트 포스트 프리뷰 포맷."""
    article = content.get("selected_article", {})
    lines = [
        "[AI Threads 프리뷰]",
        "",
        f"기사: {article.get('original_title', '?')}",
        f"선택 이유: {article.get('reason', '')}",
        "",
        "--- 메인 ---",
        content.get("post_main", ""),
        "",
        "--- 분석 ---",
        content.get("post_analysis", ""),
        "",
        "--- 첫 댓글 ---",
        content.get("post_reply", ""),
    ]
    return "\n".join(lines)


def _send_message(text):
    """텔레그램 메시지 전송."""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{TELEGRAM_API}/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": CHAT_ID, "text": text},
            )
            if resp.status_code == 200:
                print("[텔레그램] 프리뷰 전송 완료")
                return True
            print(f"[텔레그램] 전송 실패: {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"[텔레그램] 전송 에러: {e}")
        return False
