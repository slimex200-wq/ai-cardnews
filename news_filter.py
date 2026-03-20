import re
from config import AI_KEYWORDS

# 단어 경계가 필요한 짧은 키워드 (오탐 방지)
_WORD_BOUNDARY_KEYWORDS = {"ai", "nlp", "llm", "gpt"}


def _matches_keyword(text, keyword):
    if keyword in _WORD_BOUNDARY_KEYWORDS:
        return bool(re.search(rf"\b{re.escape(keyword)}\b", text))
    return keyword in text


def filter_by_keywords(articles, keywords=None, max_count=10):
    keywords = keywords or AI_KEYWORDS
    lower_keywords = [k.lower() for k in keywords]
    matched = []

    for article in articles:
        text = (article.get("title", "") + " " + article.get("summary", "")).lower()
        if any(_matches_keyword(text, kw) for kw in lower_keywords):
            matched.append(article)

    return matched[:max_count]
