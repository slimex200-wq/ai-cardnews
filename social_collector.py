"""Reddit/X 소셜 뉴스 수집 모듈.

ScrapeCreators API(Reddit) + xAI Responses API(X)로 AI 뉴스 트렌드를 수집.
rss_collector와 동일한 {title, summary, source, link} 형식 반환.
"""

import json
import os
import sys
import urllib.error
import urllib.request
import urllib.parse

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────

SCRAPECREATORS_API_KEY = os.environ.get("SCRAPECREATORS_API_KEY", "")
SCRAPECREATORS_BASE = "https://api.scrapecreators.com/v1/reddit"

SCRAPECREATORS_X_BASE = "https://api.scrapecreators.com/v1/twitter/search"


# ─────────────────────────────────────────────
# HTTP 헬퍼
# ─────────────────────────────────────────────

def _http_get(url, headers=None, timeout=20):
    """GET 요청 → JSON 반환."""
    req = urllib.request.Request(url)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _http_post(url, payload, headers=None, timeout=30):
    """POST 요청 → JSON 반환."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


# ─────────────────────────────────────────────
# Reddit (ScrapeCreators API)
# ─────────────────────────────────────────────

def collect_reddit(queries=None, max_count=15):
    """Reddit에서 AI 뉴스 수집."""
    if not SCRAPECREATORS_API_KEY:
        print("[Reddit] SCRAPECREATORS_API_KEY 미설정, 건너뜀")
        return []

    queries = queries or ["artificial intelligence", "machine learning"]
    headers = {"x-api-key": SCRAPECREATORS_API_KEY}
    articles = []
    seen_titles = set()

    for query in queries:
        params = urllib.parse.urlencode({
            "query": query,
            "sort": "relevance",
            "time_filter": "week",
            "limit": 15,
        })
        url = f"{SCRAPECREATORS_BASE}/search?{params}"
        try:
            data = _http_get(url, headers=headers, timeout=45)
        except Exception as e:
            print(f"  [Reddit] 검색 실패 ({query[:30]}): {e}")
            continue

        posts = data.get("posts", []) if isinstance(data, dict) else data
        for post in posts:
            title = post.get("title", "")
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)

            subreddit = post.get("subreddit", "reddit")
            selftext = post.get("selftext", "") or post.get("body", "")
            summary = selftext[:300] if selftext else title
            link = post.get("url", "") or post.get("permalink", "")
            if link and link.startswith("/r/"):
                link = f"https://reddit.com{link}"

            articles.append({
                "title": title,
                "summary": summary,
                "source": f"r/{subreddit}",
                "link": link,
                "_score": post.get("score", 0) or post.get("ups", 0),
            })

    articles.sort(key=lambda a: a.get("_score", 0), reverse=True)
    for a in articles:
        a.pop("_score", None)

    print(f"  -> Reddit {len(articles[:max_count])}개 수집")
    return articles[:max_count]


# ─────────────────────────────────────────────
# X/Twitter (ScrapeCreators API)
# ─────────────────────────────────────────────

def collect_x(queries=None, max_count=15):
    """X/Twitter에서 AI 뉴스 수집 (ScrapeCreators API)."""
    if not SCRAPECREATORS_API_KEY:
        print("[X] SCRAPECREATORS_API_KEY 미설정, 건너뜀")
        return []

    queries = queries or ["artificial intelligence", "AI"]
    headers = {"x-api-key": SCRAPECREATORS_API_KEY}
    articles = []
    seen = set()

    for query in queries:
        params = urllib.parse.urlencode({
            "query": query,
            "sort_by": "relevance",
        })
        url = f"{SCRAPECREATORS_X_BASE}?{params}"
        try:
            data = _http_get(url, headers=headers, timeout=45)
        except Exception as e:
            print(f"  [X] 검색 실패 ({query[:30]}): {e}")
            continue

        tweets = data.get("tweets") or data.get("data") or data.get("results") or []
        for tweet in tweets:
            text = tweet.get("full_text") or tweet.get("text") or ""
            if not text or text[:50] in seen:
                continue
            seen.add(text[:50])

            user = tweet.get("user") or tweet.get("author") or {}
            author = user.get("screen_name") or user.get("username") or ""
            tweet_id = tweet.get("id") or tweet.get("id_str") or ""
            link = f"https://x.com/{author}/status/{tweet_id}" if author and tweet_id else ""
            likes = tweet.get("favorite_count") or tweet.get("likes") or 0

            lines = text.strip().split("\n")
            title = lines[0][:120] if lines else text[:120]

            articles.append({
                "title": title,
                "summary": text[:300],
                "source": f"X/@{author}" if author else "X",
                "link": link,
                "_score": likes,
            })

    articles.sort(key=lambda a: a.get("_score", 0), reverse=True)
    for a in articles:
        a.pop("_score", None)

    print(f"  -> X {len(articles[:max_count])}개 수집")
    return articles[:max_count]


# ─────────────────────────────────────────────
# 통합 수집
# ─────────────────────────────────────────────

def collect_social(max_count=30):
    """Reddit + X에서 AI 뉴스 통합 수집."""
    print("[소셜] Reddit/X AI 뉴스 수집 중...")

    reddit_articles = collect_reddit(
        queries=["artificial intelligence", "machine learning", "ChatGPT"],
        max_count=15,
    )
    # X 수집 비활성화 (Windows Bird search 인코딩 이슈 + ScrapeCreators 빈 결과)
    # TODO: Linux 환경 또는 ScrapeCreators 복구 후 재활성화
    x_articles = []
    # x_articles = collect_x(
    #     queries=["artificial intelligence", "ChatGPT"],
    #     max_count=15,
    # )

    combined = reddit_articles + x_articles

    # 제목 중복 제거
    seen = set()
    unique = []
    for a in combined:
        key = a["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(a)

    print(f"[소셜] 총 {len(unique[:max_count])}개 (Reddit {len(reddit_articles)} + X {len(x_articles)})")
    return unique[:max_count]


if __name__ == "__main__":
    articles = collect_social()
    for i, a in enumerate(articles, 1):
        print(f"\n[{i}] {a['title']}")
        print(f"    소스: {a['source']}")
        print(f"    링크: {a['link']}")
