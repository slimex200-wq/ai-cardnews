"""멀티소스 AI 뉴스 수집 모듈.

last30days 스킬의 수집 모듈을 활용하여 10개 소스에서 AI 뉴스를 수집.
rss_collector와 동일한 {title, summary, source, link} 형식 반환.

소스 (키 불필요):
  - Hacker News (Algolia API)
  - YouTube (yt-dlp)
  - Polymarket (Gamma API)

소스 (SCRAPECREATORS_API_KEY):
  - Reddit
  - TikTok
  - Instagram

소스 (별도 키):
  - Bluesky (BSKY_HANDLE + BSKY_APP_PASSWORD)
  - Truth Social (TRUTHSOCIAL_TOKEN)

제외:
  - X/Twitter (Windows 인코딩 이슈)
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

# last30days 스킬 라이브러리 경로 추가
_SKILL_LIB = Path.home() / ".claude" / "skills" / "last30days" / "scripts"
if _SKILL_LIB.exists() and str(_SKILL_LIB) not in sys.path:
    sys.path.insert(0, str(_SKILL_LIB))

# AI 뉴스 검색 쿼리
AI_TOPIC = "artificial intelligence AI LLM"
AI_QUERIES = ["artificial intelligence", "machine learning", "ChatGPT", "LLM"]

# 날짜 범위 (최근 2일)
_TODAY = date.today().isoformat()
_FROM = (date.today() - timedelta(days=2)).isoformat()


def _normalize(items, source_name, title_key="title", summary_key=None,
               link_key="url", score_fn=None):
    """last30days 결과를 {title, summary, source, link, _score} 형식으로 변환."""
    articles = []
    for item in items:
        title = item.get(title_key, "") or ""
        if not title:
            # text 필드 폴백 (TikTok, Instagram, Bluesky, Truth Social)
            title = (item.get("text", "") or "")[:120]
        if not title:
            continue

        summary = ""
        if summary_key:
            summary = item.get(summary_key, "") or ""
        if not summary:
            summary = item.get("text", "") or item.get("selftext", "") or title
        summary = summary[:400]

        link = item.get(link_key, "") or item.get("hn_url", "") or ""

        # 소스 라벨
        author = item.get("author_name", "") or item.get("handle", "") or ""
        if author:
            label = f"{source_name}/@{author}"
        elif item.get("subreddit"):
            label = f"r/{item['subreddit']}"
        elif item.get("channel_name"):
            label = f"YouTube/{item['channel_name']}"
        else:
            label = source_name

        score = score_fn(item) if score_fn else 0

        articles.append({
            "title": title,
            "summary": summary,
            "source": label,
            "link": link,
            "_score": score,
        })

    return articles


# ─────────────────────────────────────────────
# 개별 소스 수집 함수
# ─────────────────────────────────────────────

def _collect_reddit():
    """Reddit 수집 (ScrapeCreators)."""
    try:
        from lib.reddit import search_reddit
        result = search_reddit(AI_TOPIC, _FROM, _TODAY, depth="quick")
        items = result.get("items", [])
        return _normalize(
            items, "Reddit",
            score_fn=lambda i: i.get("engagement", {}).get("score", 0),
        )
    except Exception as e:
        print(f"  [Reddit] 실패: {e}")
        return []


def _collect_hackernews():
    """Hacker News 수집 (무료 Algolia API)."""
    try:
        from lib.hackernews import search_hackernews
        result = search_hackernews(AI_TOPIC, _FROM, _TODAY, depth="quick")
        items = result.get("hits", [])
        return _normalize(
            items, "HN",
            score_fn=lambda i: i.get("engagement", {}).get("points", 0),
        )
    except Exception as e:
        print(f"  [HN] 실패: {e}")
        return []


def _collect_youtube():
    """YouTube 수집 (yt-dlp)."""
    try:
        from lib.youtube_yt import search_youtube, is_ytdlp_installed
        if not is_ytdlp_installed():
            print("  [YouTube] yt-dlp 미설치, 건너뜀")
            return []
        result = search_youtube(AI_TOPIC, _FROM, _TODAY, depth="quick")
        items = result.get("items", [])
        return _normalize(
            items, "YouTube",
            link_key="url",
            score_fn=lambda i: i.get("engagement", {}).get("views", 0),
        )
    except Exception as e:
        print(f"  [YouTube] 실패: {e}")
        return []


def _collect_tiktok():
    """TikTok 수집 (ScrapeCreators)."""
    try:
        from lib.tiktok import search_tiktok
        result = search_tiktok(AI_TOPIC, _FROM, _TODAY, depth="quick")
        items = result.get("items", [])
        return _normalize(
            items, "TikTok",
            title_key="text",
            score_fn=lambda i: i.get("engagement", {}).get("views", 0),
        )
    except Exception as e:
        print(f"  [TikTok] 실패: {e}")
        return []


def _collect_instagram():
    """Instagram 수집 (ScrapeCreators)."""
    try:
        from lib.instagram import search_instagram
        result = search_instagram(AI_TOPIC, _FROM, _TODAY, depth="quick")
        items = result.get("items", [])
        return _normalize(
            items, "Instagram",
            title_key="text",
            score_fn=lambda i: i.get("engagement", {}).get("views", 0),
        )
    except Exception as e:
        print(f"  [Instagram] 실패: {e}")
        return []


def _collect_hackernews_free():
    """Hacker News — 별도 함수 (키 불필요 보장)."""
    return _collect_hackernews()


def _collect_bluesky():
    """Bluesky 수집."""
    try:
        from lib.bluesky import search_bluesky
        result = search_bluesky(AI_TOPIC, _FROM, _TODAY, depth="quick")
        items = result.get("posts", [])
        return _normalize(
            items, "Bluesky",
            title_key="text",
            score_fn=lambda i: i.get("engagement", {}).get("likes", 0),
        )
    except Exception as e:
        print(f"  [Bluesky] 실패: {e}")
        return []


def _collect_truthsocial():
    """Truth Social 수집."""
    try:
        from lib.truthsocial import search_truthsocial
        result = search_truthsocial(AI_TOPIC, _FROM, _TODAY, depth="quick")
        items = result.get("statuses", [])
        return _normalize(
            items, "TruthSocial",
            title_key="text",
            score_fn=lambda i: i.get("engagement", {}).get("likes", 0),
        )
    except Exception as e:
        print(f"  [TruthSocial] 실패: {e}")
        return []


def _collect_polymarket():
    """Polymarket 수집 (무료 Gamma API). AI 관련 예측 시장."""
    try:
        from lib.polymarket import search_polymarket
        result = search_polymarket(AI_TOPIC, _FROM, _TODAY, depth="quick")
        events = result.get("events", [])
        articles = []
        for ev in events:
            title = ev.get("title", "")
            if not title:
                continue
            articles.append({
                "title": title,
                "summary": ev.get("description", title)[:400],
                "source": "Polymarket",
                "link": f"https://polymarket.com/event/{ev.get('id', '')}",
                "_score": 0,
            })
        return articles
    except Exception as e:
        print(f"  [Polymarket] 실패: {e}")
        return []


# ─────────────────────────────────────────────
# 통합 수집
# ─────────────────────────────────────────────

# 소스별 최대 수집 수
_SOURCE_LIMITS = {
    "Reddit": 15,
    "HN": 10,
    "YouTube": 8,
    "TikTok": 8,
    "Instagram": 8,
    "Bluesky": 8,
    "TruthSocial": 5,
    "Polymarket": 5,
}

_COLLECTORS = [
    ("Reddit", _collect_reddit),
    ("HN", _collect_hackernews),
    ("YouTube", _collect_youtube),
    ("TikTok", _collect_tiktok),
    ("Instagram", _collect_instagram),
    ("Bluesky", _collect_bluesky),
    ("TruthSocial", _collect_truthsocial),
    ("Polymarket", _collect_polymarket),
]


def collect_social(max_count=50):
    """8개 소스에서 AI 뉴스 병렬 수집."""
    print("[소셜] 멀티소스 AI 뉴스 수집 중...")

    all_articles = []
    source_counts = {}

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(fn): name
            for name, fn in _COLLECTORS
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                articles = future.result(timeout=60)
                limit = _SOURCE_LIMITS.get(name, 10)
                # 인게이지먼트 높은 순 정렬 후 제한
                articles.sort(key=lambda a: a.get("_score", 0), reverse=True)
                articles = articles[:limit]
                source_counts[name] = len(articles)
                all_articles.extend(articles)
            except Exception as e:
                print(f"  [{name}] 타임아웃/에러: {e}")
                source_counts[name] = 0

    # _score 제거
    for a in all_articles:
        a.pop("_score", None)

    # 제목 중복 제거 (정규화 비교)
    from history import normalize_title
    seen = set()
    unique = []
    for a in all_articles:
        key = normalize_title(a["title"])
        if key not in seen:
            seen.add(key)
            unique.append(a)

    # 결과 요약
    active = {k: v for k, v in source_counts.items() if v > 0}
    summary = ", ".join(f"{k} {v}" for k, v in active.items())
    print(f"[소셜] 총 {len(unique[:max_count])}개 ({summary})")

    return unique[:max_count]


if __name__ == "__main__":
    articles = collect_social()
    for i, a in enumerate(articles, 1):
        print(f"\n[{i}] {a['title'][:80]}")
        print(f"    소스: {a['source']}")
        print(f"    링크: {a['link'][:80]}")
