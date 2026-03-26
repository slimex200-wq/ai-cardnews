"""AI Threads — 8개 소스에서 트렌딩 AI 뉴스 1개를 골라 Threads 바이럴 포스트.

Usage:
    python main.py              # 수집 → 생성 → 포스팅
    python main.py --dry-run    # 포스팅 없이 생성만
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from config import ANTHROPIC_API_KEY, THREADS_ACCESS_TOKEN, THREADS_USER_ID


def main():
    parser = argparse.ArgumentParser(description="AI Threads 바이럴 포스트")
    parser.add_argument("--dry-run", action="store_true", help="포스팅 없이 생성만")
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        print("[에러] ANTHROPIC_API_KEY 미설정")
        sys.exit(1)
    if not args.dry_run and (not THREADS_ACCESS_TOKEN or not THREADS_USER_ID):
        print("[에러] THREADS_ACCESS_TOKEN 또는 THREADS_USER_ID 미설정")
        sys.exit(1)

    # 1. 멀티소스 수집 (소셜 주력 + RSS 보충)
    print("[1/4] 8개 소스에서 AI 뉴스 수집 중...")
    from social_collector import collect_social
    from rss_collector import collect_news

    articles = []
    try:
        articles = collect_social(max_count=30)
    except Exception as e:
        print(f"  소셜 수집 실패: {e}")

    rss = collect_news(max_count=50)
    if rss:
        articles = articles + rss
        print(f"  RSS {len(rss)}개 보충, 총 {len(articles)}개")

    if not articles:
        print("[에러] 뉴스를 수집하지 못했습니다.")
        sys.exit(1)

    # 2. AI 키워드 필터링
    print(f"\n[2/4] AI 관련 기사 필터링 중...")
    from news_filter import filter_by_keywords
    filtered = filter_by_keywords(articles, max_count=15) or articles[:15]
    print(f"  {len(filtered)}개 기사 통과")

    # 3. 텍스트 포스트 생성
    print(f"\n[3/4] 바이럴 포스트 생성 중...")
    from history import load_used_titles, save_title
    from ai_writer import generate_post

    content = generate_post(filtered, used_titles=load_used_titles())

    article = content.get("selected_article", {})
    print(f"  선택: {article.get('original_title', '?')}")
    print(f"  이유: {article.get('reason', '')}")

    # 저장
    out_dir = Path("output") / date.today().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "post.json").write_text(
        json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    from telegram_notify import send_preview
    send_preview(content)

    if args.dry_run:
        print("\n[dry-run] 포스팅 건너뜀")
        return

    # 4. Threads 포스팅
    print(f"\n[4/4] Threads 포스팅 중...")
    from threads_poster import post_text
    result = post_text(
        access_token=THREADS_ACCESS_TOKEN,
        user_id=THREADS_USER_ID,
        main_text=content["post_main"],
        reply_text=content.get("post_reply"),
    )
    print(f"  포스팅 완료!")

    if article.get("original_title"):
        save_title(article["original_title"])

    from telegram_notify import send_result
    send_result(result)


if __name__ == "__main__":
    main()
