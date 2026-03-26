"""Threads 하이브리드 포스팅 모듈 — 텍스트 후킹 + 캐러셀 카드뉴스.

3단계 포스팅 전략:
  1) 텍스트 메인 포스트 (의견 + 질문) → 도달률 담당
  2) 본인 첫 댓글 (부연 의견) → 대화 시작 신호
  3) 본인 두 번째 댓글 (캐러셀 카드뉴스) → 브랜딩 담당 (딜레이 후)

사용법:
  # 풀 파이프라인: 뉴스수집 → 카드뉴스 생성 → 텍스트 생성 → 포스팅
  python threads_text_poster.py

  # 텍스트만 (카드뉴스 없이)
  python threads_text_poster.py --text-only

  # 포스팅 없이 생성만
  python threads_text_poster.py --dry-run

  # 이미 카드뉴스가 생성된 날짜 지정
  python threads_text_poster.py --skip-cardnews --date 2026-03-25

  # 캐러셀 딜레이 조절 (기본 10분)
  python threads_text_poster.py --carousel-delay 600
"""

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import httpx

from config import ANTHROPIC_API_KEY
from rss_collector import collect_news
from news_filter import filter_by_keywords

GRAPH_API_BASE = "https://graph.threads.net/v1.0"
PUBLISH_RETRY_ATTEMPTS = 5
PUBLISH_RETRY_DELAY = 3
CONTAINER_WAIT_DELAY = 2
TRANSIENT_RETRY_ATTEMPTS = 3
TRANSIENT_RETRY_DELAY = 5

# 기본 딜레이 설정
FIRST_REPLY_DELAY = 5          # 메인 → 첫 댓글 (초)
CAROUSEL_REPLY_DELAY = 600     # 메인 → 캐러셀 댓글 (초, 기본 10분)


# ─────────────────────────────────────────────
# Threads API 헬퍼
# ─────────────────────────────────────────────

def _is_retryable(response):
    """재시도 가능한 에러인지 판단."""
    if response.status_code >= 500:
        return True
    if response.status_code == 400:
        try:
            error = response.json().get("error", {})
        except Exception:
            return False
        return error.get("code") == 24 and error.get("error_subcode") == 4279009
    return False


def create_text_container(client, user_id, access_token, text, reply_to_id=""):
    """텍스트 컨테이너 생성."""
    params = {
        "media_type": "TEXT",
        "text": text,
        "access_token": access_token,
    }
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    response = client.post(f"{GRAPH_API_BASE}/{user_id}/threads", params=params)
    if response.status_code >= 400:
        raise RuntimeError(f"create text container failed: {response.status_code} {response.text[:500]}")
    return response.json()["id"]


def create_image_container(client, user_id, access_token, image_url):
    """단일 이미지 컨테이너 생성 (재시도 포함)."""
    response = None
    for attempt in range(1, TRANSIENT_RETRY_ATTEMPTS + 1):
        response = client.post(
            f"{GRAPH_API_BASE}/{user_id}/threads",
            params={
                "media_type": "IMAGE",
                "image_url": image_url,
                "access_token": access_token,
            },
        )
        if response.status_code < 400:
            return response.json()["id"]
        if attempt < TRANSIENT_RETRY_ATTEMPTS and _is_retryable(response):
            print(f"  → 이미지 컨테이너 재시도 {attempt}/{TRANSIENT_RETRY_ATTEMPTS}...")
            time.sleep(TRANSIENT_RETRY_DELAY)
            continue
        break
    raise RuntimeError(f"create image container failed: {response.status_code} {response.text[:500]}")


def create_carousel_reply_container(client, user_id, access_token, children_ids, reply_to_id):
    """캐러셀 댓글 컨테이너 생성."""
    response = client.post(
        f"{GRAPH_API_BASE}/{user_id}/threads",
        params={
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "reply_to_id": reply_to_id,
            "access_token": access_token,
        },
    )
    if response.status_code >= 400:
        raise RuntimeError(f"create carousel reply failed: {response.status_code} {response.text[:500]}")
    return response.json()["id"]


def publish_container(client, user_id, access_token, creation_id):
    """컨테이너 발행 (재시도 포함)."""
    response = None
    for attempt in range(1, PUBLISH_RETRY_ATTEMPTS + 1):
        response = client.post(
            f"{GRAPH_API_BASE}/{user_id}/threads_publish",
            params={"creation_id": creation_id, "access_token": access_token},
        )
        if response.status_code < 400:
            return response.json()["id"]
        if attempt < PUBLISH_RETRY_ATTEMPTS and _is_retryable(response):
            print(f"  → 발행 재시도 {attempt}/{PUBLISH_RETRY_ATTEMPTS}...")
            time.sleep(PUBLISH_RETRY_DELAY)
            continue
        break
    raise RuntimeError(f"publish failed: {response.status_code} {response.text[:500]}")


def check_url_accessible(url, timeout=10):
    """URL 접근 가능 여부 확인."""
    try:
        resp = httpx.head(url, timeout=timeout, follow_redirects=True)
        return resp.status_code == 200
    except Exception:
        return False


# ─────────────────────────────────────────────
# 3단계 포스팅 메인 로직
# ─────────────────────────────────────────────

def post_hybrid(
    access_token,
    user_id,
    main_text,
    reply_text=None,
    carousel_image_urls=None,
    carousel_delay=CAROUSEL_REPLY_DELAY,
):
    """하이브리드 포스팅: 텍스트 → 첫 댓글 → (딜레이) → 캐러셀 댓글.

    Args:
        main_text: 메인 텍스트 포스트
        reply_text: 본인 첫 댓글 (의견)
        carousel_image_urls: 캐러셀 이미지 URL 목록 (None이면 텍스트 온리)
        carousel_delay: 캐러셀 댓글 딜레이 (초)

    Returns:
        {"post_id": str, "reply_id": str | None, "carousel_id": str | None}
    """
    total_steps = 3 if carousel_image_urls else 2

    with httpx.Client(timeout=30.0) as client:
        # ── Step 1: 텍스트 메인 포스트 ──
        print(f"[Step 1/{total_steps}] 텍스트 메인 포스트 발행 중...")
        main_container = create_text_container(client, user_id, access_token, main_text)
        time.sleep(CONTAINER_WAIT_DELAY)
        post_id = publish_container(client, user_id, access_token, main_container)
        print(f"  ✓ 메인 포스트: {post_id}")

        # ── Step 2: 본인 첫 댓글 (부연 의견) ──
        reply_id = None
        if reply_text:
            print(f"\n[Step 2/{total_steps}] 첫 댓글 작성 중... ({FIRST_REPLY_DELAY}초 대기)")
            time.sleep(FIRST_REPLY_DELAY)
            reply_container = create_text_container(
                client, user_id, access_token, reply_text, reply_to_id=post_id
            )
            time.sleep(CONTAINER_WAIT_DELAY)
            reply_id = publish_container(client, user_id, access_token, reply_container)
            print(f"  ✓ 첫 댓글: {reply_id}")

        # ── Step 3: 캐러셀 카드뉴스 댓글 (딜레이 후) ──
        carousel_id = None
        if carousel_image_urls:
            delay_min = carousel_delay // 60
            delay_sec = carousel_delay % 60
            delay_str = f"{delay_min}분" if delay_sec == 0 else f"{delay_min}분 {delay_sec}초"
            print(f"\n[Step 3/{total_steps}] 캐러셀 댓글 대기 중... ({delay_str})")
            print(f"  💡 이 시간 동안 다른 포스트에 댓글 달러 가세요!")

            # 카운트다운 (1분 간격으로 상태 표시)
            remaining = carousel_delay
            while remaining > 0:
                wait = min(remaining, 60)
                time.sleep(wait)
                remaining -= wait
                if remaining > 0:
                    print(f"  → 남은 시간: {remaining // 60}분 {remaining % 60}초")

            print(f"\n  캐러셀 이미지 컨테이너 생성 중... ({len(carousel_image_urls)}장)")
            children_ids = []
            for i, url in enumerate(carousel_image_urls, 1):
                cid = create_image_container(client, user_id, access_token, url)
                children_ids.append(cid)
                print(f"  → 이미지 {i}/{len(carousel_image_urls)}: {cid}")

            time.sleep(CONTAINER_WAIT_DELAY)
            carousel_container = create_carousel_reply_container(
                client, user_id, access_token, children_ids, reply_to_id=post_id
            )
            time.sleep(CONTAINER_WAIT_DELAY)
            carousel_id = publish_container(client, user_id, access_token, carousel_container)
            print(f"  ✓ 캐러셀 댓글: {carousel_id}")

    return {"post_id": post_id, "reply_id": reply_id, "carousel_id": carousel_id}


# ─────────────────────────────────────────────
# 히스토리 로드
# ─────────────────────────────────────────────

def _load_history(output_base):
    """히스토리에서 사용된 제목 로드."""
    from cardnews import _load_history as load_hist
    _, used_titles = load_hist(output_base)
    return used_titles


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Threads 하이브리드 포스팅 (텍스트 + 캐러셀)")
    parser.add_argument("--output", type=str, default="output", help="output 디렉토리 경로")
    parser.add_argument("--date", type=str, default=date.today().isoformat(),
                        help="카드뉴스 날짜 (YYYY-MM-DD, 기본: 오늘)")
    parser.add_argument("--base-url", type=str,
                        default="https://slimex200-wq.github.io/ai-cardnews",
                        help="GitHub Pages base URL")
    parser.add_argument("--text-only", action="store_true",
                        help="캐러셀 없이 텍스트만 포스팅")
    parser.add_argument("--carousel-delay", type=int, default=CAROUSEL_REPLY_DELAY,
                        help=f"캐러셀 댓글 딜레이 초 (기본: {CAROUSEL_REPLY_DELAY})")
    parser.add_argument("--dry-run", action="store_true", help="포스팅 없이 생성만")
    parser.add_argument("--skip-cardnews", action="store_true",
                        help="카드뉴스 생성 건너뛰기 (이미 생성된 경우)")
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        print("[에러] ANTHROPIC_API_KEY 환경변수를 설정해주세요.")
        sys.exit(1)

    access_token = os.environ.get("THREADS_ACCESS_TOKEN", "")
    user_id = os.environ.get("THREADS_USER_ID", "")

    if not args.dry_run and (not access_token or not user_id):
        print("[에러] THREADS_ACCESS_TOKEN 또는 THREADS_USER_ID 미설정")
        sys.exit(1)

    # ── 1. 뉴스 수집 (RSS + 소셜) ──
    print("[1/5] AI 뉴스 수집 중...")
    articles = collect_news(max_count=50)
    print(f"  → RSS {len(articles)}개 수집")

    # 소셜 (Reddit/X) 수집 병합
    try:
        from social_collector import collect_social
        social_articles = collect_social(max_count=20)
        if social_articles:
            articles = social_articles + articles  # 소셜 우선
    except Exception as e:
        print(f"  [소셜] 수집 실패, RSS만 사용: {e}")

    if not articles:
        print("[에러] 뉴스를 수집하지 못했습니다.")
        sys.exit(1)
    print(f"  → 총 {len(articles)}개 기사")

    # ── 2. 필터링 ──
    print("[2/5] AI 관련 기사 필터링 중...")
    filtered = filter_by_keywords(articles, max_count=10)
    if not filtered:
        filtered = articles[:10]
    print(f"  → {len(filtered)}개 기사 통과")

    used_titles = _load_history(args.output)

    # ── 3. 카드뉴스 생성 (기존 파이프라인) ──
    carousel_image_urls = None
    output_dir = Path(args.output) / args.date

    if not args.text_only:
        if args.skip_cardnews:
            print("[3/5] 기존 카드뉴스 사용...")
        else:
            print("[3/5] 카드뉴스 생성 중... (기존 파이프라인)")
            try:
                from image_fetcher import fetch_all_thumbnails
                from ai_writer_v2 import generate_card_content
                from card_renderer import render_cover, render_news_card, render_closing
                from cardnews import (
                    _match_images_to_cards, _get_volume_number, _save_history,
                )
                from config import get_output_dir, DEFAULT_COUNT

                filtered_with_media = fetch_all_thumbnails(filtered)
                card_content = generate_card_content(
                    filtered_with_media, select_count=DEFAULT_COUNT, used_titles=used_titles
                )
                _match_images_to_cards(card_content["cards"], filtered_with_media)

                real_output_dir = get_output_dir(args.output)
                vol_num = _get_volume_number(args.output)
                total = len(card_content["cards"])

                all_kw = []
                for c in card_content["cards"]:
                    all_kw.extend(c.get("keywords", []))
                seen_kw = set()
                unique_kw = [k for k in all_kw if k not in seen_kw and not seen_kw.add(k)]

                cover_banner = None
                for c in card_content["cards"]:
                    if c.get("banner_b64"):
                        cover_banner = c.pop("banner_b64")
                        c.pop("thumbnail_b64", None)
                        break

                render_cover(
                    card_content.get("cover_headline", "오늘의 AI 뉴스"),
                    card_content["cover_date"], real_output_dir, total,
                    keywords=unique_kw[:4], vol_num=vol_num,
                    trend_summary=card_content.get("trend_summary", ""),
                    banner_b64=cover_banner,
                )
                for i, card in enumerate(card_content["cards"], 2):
                    render_news_card(card, i, real_output_dir, total)
                render_closing(
                    card_content["closing_message"], total + 2, real_output_dir, total
                )

                used_links = [c.get("link", "") for c in card_content["cards"] if c.get("link")]
                used_t = [c.get("original_title", "") for c in card_content["cards"] if c.get("original_title")]
                _save_history(args.output, used_links, used_t)

                output_dir = real_output_dir
                print(f"  → 카드뉴스 생성 완료: {output_dir}")

            except Exception as e:
                print(f"  ⚠ 카드뉴스 생성 실패: {e}")
                print(f"  → 텍스트 온리로 전환합니다.")
                args.text_only = True

        # 카드 이미지 URL 준비
        if not args.text_only and output_dir.exists():
            card_files = sorted(output_dir.glob("card-*.png"))
            if card_files:
                carousel_image_urls = [
                    f"{args.base_url}/cards/{args.date}/{f.name}" for f in card_files
                ]
                print(f"  → 캐러셀 이미지 {len(carousel_image_urls)}장 준비")
            else:
                print("  ⚠ 카드 이미지 없음, 텍스트 온리로 전환")
    else:
        print("[3/5] 텍스트 온리 모드 — 카드뉴스 건너뜀")

    # ── 4. 텍스트 포스트 생성 ──
    print("[4/5] 텍스트 포스트 생성 중... (Claude API)")
    from ai_writer_v2 import generate_text_post
    content = generate_text_post(filtered, used_titles=used_titles)

    print(f"\n{'='*50}")
    print(f"📰 선택 기사: {content['selected_article']['original_title']}")
    print(f"💡 선택 이유: {content['selected_article']['reason']}")
    print(f"{'='*50}")
    print(f"\n📝 메인 포스트:\n{content['post_main']}")
    print(f"\n💬 첫 댓글:\n{content['post_reply']}")
    if carousel_image_urls:
        print(f"\n🖼️ 캐러셀: {len(carousel_image_urls)}장 → {args.carousel_delay // 60}분 뒤 대댓글")
    else:
        print(f"\n🖼️ 캐러셀: 없음 (텍스트 온리)")
    print(f"\n🏷️ 태그: {content.get('topic_tag', 'AI 뉴스')}")
    print(f"{'='*50}")

    # 저장
    output_dir.mkdir(parents=True, exist_ok=True)
    text_file = output_dir / "text_post.json"
    text_file.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  → 저장: {text_file}")

    # 텔레그램 프리뷰 전송
    from telegram_notify import send_preview
    send_preview(content, mode="text")

    if args.dry_run:
        print("\n[dry-run] 포스팅 건너뜀")
        return

    # ── 5. Threads 포스팅 ──
    print("\n[5/5] Threads 하이브리드 포스팅 시작!")
    result = post_hybrid(
        access_token=access_token,
        user_id=user_id,
        main_text=content["post_main"],
        reply_text=content.get("post_reply"),
        carousel_image_urls=carousel_image_urls,
        carousel_delay=args.carousel_delay,
    )

    print(f"\n{'='*50}")
    print(f"[Threads] 포스팅 완료!")
    print(f"  ✓ 메인 포스트: {result['post_id']}")
    if result["reply_id"]:
        print(f"  ✓ 첫 댓글: {result['reply_id']}")
    if result["carousel_id"]:
        print(f"  ✓ 캐러셀 댓글: {result['carousel_id']}")
    print(f"{'='*50}")

    # 텔레그램 포스팅 결과 전송
    from telegram_notify import send_result
    send_result(result)


if __name__ == "__main__":
    main()
