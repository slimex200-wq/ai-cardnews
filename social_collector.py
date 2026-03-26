"""Reddit/X 소셜 뉴스 수집 모듈.

ScrapeCreators API(Reddit) + xAI Responses API(X)로 AI 뉴스 트렌드를 수집.
rss_collector와 동일한 {title, summary, source, link} 형식 반환.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
import urllib.parse
from datetime import date, datetime, timedelta, timezone

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────

SCRAPECREATORS_API_KEY = os.environ.get("SCRAPECREATORS_API_KEY", "")
SCRAPECREATORS_BASE = "https://api.scrapecreators.com/v1/reddit"

XAI_API_KEY = os.environ.get("XAI_API_KEY", "")
XAI_RESPONSES_URL = "https://api.x.ai/v1/responses"
XAI_MODEL = "grok-3-mini"


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
# X/Twitter (xAI Responses API + x_search tool)
# ─────────────────────────────────────────────

X_SEARCH_PROMPT = """Search X/Twitter for the most discussed posts about: {topic}

Focus on posts from {from_date} to {to_date}. Find 10-15 high-quality posts.

Return ONLY valid JSON:
{{
  "items": [
    {{
      "text": "Post text",
      "url": "https://x.com/user/status/...",
      "author_handle": "username",
      "likes": 100,
      "reposts": 25
    }}
  ]
}}

Rules:
- Prefer posts with substantive content, opinions, or breaking news
- Include diverse voices
- Korean AI community posts are welcome"""


def collect_x(queries=None, max_count=15):
    """X/Twitter에서 AI 뉴스 수집 (xAI Responses API)."""
    if not XAI_API_KEY:
        print("[X] XAI_API_KEY 미설정, 건너뜀")
        return []

    queries = queries or ["AI news breakthrough controversy"]
    today = date.today().isoformat()
    from_date = (date.today() - timedelta(days=2)).isoformat()
    headers = {"Authorization": f"Bearer {XAI_API_KEY}"}
    articles = []
    seen = set()

    for query in queries:
        payload = {
            "model": XAI_MODEL,
            "tools": [{"type": "x_search", "from_date": from_date, "to_date": today}],
            "input": [
                {
                    "role": "user",
                    "content": X_SEARCH_PROMPT.format(
                        topic=query, from_date=from_date, to_date=today,
                    ),
                }
            ],
        }
        try:
            data = _http_post(XAI_RESPONSES_URL, payload, headers=headers, timeout=60)
        except Exception as e:
            print(f"  [X] 검색 실패: {e}")
            continue

        # 응답에서 텍스트 추출
        output_text = ""
        for item in data.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        output_text = content.get("text", "")

        if not output_text:
            continue

        # JSON 추출
        match = re.search(r"\{.*\}", output_text, re.DOTALL)
        if not match:
            continue
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue

        for post in parsed.get("items", []):
            text = post.get("text", "")
            if not text or text[:50] in seen:
                continue
            seen.add(text[:50])

            lines = text.strip().split("\n")
            title = lines[0][:120] if lines else text[:120]
            author = post.get("author_handle", "")
            link = post.get("url", "")

            articles.append({
                "title": title,
                "summary": text[:300],
                "source": f"X/@{author}" if author else "X",
                "link": link,
            })

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
    x_articles = collect_x(
        queries=["AI news trending today 2026"],
        max_count=15,
    )

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
