"""텔레그램 프리뷰 알림 모듈."""

import os
import httpx

TELEGRAM_API = "https://api.telegram.org"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def send_preview(content, mode="text"):
    """생성된 포스트 프리뷰를 텔레그램으로 전송.

    Args:
        content: generate_text_post() 또는 generate_card_content() 결과
        mode: "text" (텍스트 포스트) 또는 "card" (카드뉴스)
    """
    if not BOT_TOKEN or not CHAT_ID:
        print("[텔레그램] BOT_TOKEN 또는 CHAT_ID 미설정, 알림 건너뜀")
        return False

    if mode == "text":
        message = _format_text_preview(content)
    else:
        message = _format_card_preview(content)

    return _send_message(message)


def send_result(result):
    """포스팅 완료 결과를 텔레그램으로 전송."""
    if not BOT_TOKEN or not CHAT_ID:
        return False

    lines = ["[포스팅 완료]"]
    if result.get("post_id"):
        lines.append(f"메인: {result['post_id']}")
    if result.get("reply_id"):
        lines.append(f"첫 댓글: {result['reply_id']}")
    if result.get("carousel_id"):
        lines.append(f"캐러셀: {result['carousel_id']}")

    return _send_message("\n".join(lines))


def _format_text_preview(content):
    """텍스트 포스트 프리뷰 포맷."""
    article = content.get("selected_article", {})
    lines = [
        "[AI CardNews 프리뷰]",
        "",
        f"기사: {article.get('original_title', '?')}",
        f"선택 이유: {article.get('reason', '')}",
        "",
        "--- 메인 포스트 ---",
        content.get("post_main", ""),
        "",
        "--- 첫 댓글 ---",
        content.get("post_reply", ""),
        "",
        f"태그: {content.get('topic_tag', '')}",
    ]
    return "\n".join(lines)


def _format_card_preview(content):
    """카드뉴스 프리뷰 포맷."""
    cards = content.get("cards", [])
    lines = [
        "[AI CardNews 카드뉴스 프리뷰]",
        "",
        f"헤드라인: {content.get('cover_headline', '')}",
        f"트렌드: {content.get('trend_summary', '')}",
        f"카드 {len(cards)}장",
        "",
    ]
    for i, card in enumerate(cards, 1):
        lines.append(f"{i}. {card.get('title', '')} - {card.get('subtitle', '')}")
    lines.append("")
    lines.append("--- 캡션 ---")
    lines.append(content.get("caption", ""))
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
