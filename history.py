"""포스팅 히스토리 관리 — 중복 방지."""

import json
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path

HISTORY_DAYS = 3
HISTORY_FILE = Path("output/history.json")


def normalize_title(title: str) -> str:
    """제목 정규화 — 따옴표/공백/특수문자 통일로 동일 기사 비교 정확도 향상."""
    t = unicodedata.normalize("NFC", title)
    # 모든 종류의 따옴표를 전부 제거 (', ", 스마트쿼트 등)
    t = re.sub(r"""['"''""„`\u2018\u2019\u201A\u201B\u201C\u201D\u201E\u201F]""", "", t)
    # 말줄임표 통일
    t = re.sub(r"\.{2,}", "...", t)
    t = re.sub(r"\u2026", "...", t)
    # 연속 공백 제거
    t = re.sub(r"\s+", " ", t).strip()
    return t.lower()


def load_used_titles() -> list[str]:
    """최근 HISTORY_DAYS일 내 사용된 제목 목록 (원본)."""
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError):
        return []
    cutoff = (date.today() - timedelta(days=HISTORY_DAYS)).isoformat()
    titles: list[str] = []
    for entry in data:
        if entry.get("date", "") >= cutoff:
            titles.extend(entry.get("titles", []))
    return titles


def load_used_urls() -> set[str]:
    """최근 HISTORY_DAYS일 내 사용된 URL 집합."""
    if not HISTORY_FILE.exists():
        return set()
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError):
        return set()
    cutoff = (date.today() - timedelta(days=HISTORY_DAYS)).isoformat()
    urls: set[str] = set()
    for entry in data:
        if entry.get("date", "") >= cutoff:
            urls.update(entry.get("urls", []))
    return urls


def is_duplicate(title: str, url: str = "") -> bool:
    """제목(정규화 비교) 또는 URL이 히스토리에 있으면 True."""
    used_titles = load_used_titles()
    used_urls = load_used_urls()

    if url and url in used_urls:
        return True

    norm = normalize_title(title)
    return any(normalize_title(t) == norm for t in used_titles)


def filter_duplicates(articles: list[dict]) -> list[dict]:
    """기사 리스트에서 히스토리와 중복되는 항목 제거."""
    used_titles = load_used_titles()
    used_urls = load_used_urls()
    norm_used = {normalize_title(t) for t in used_titles}

    result: list[dict] = []
    for a in articles:
        url = a.get("link", "")
        if url and url in used_urls:
            continue
        if normalize_title(a.get("title", "")) in norm_used:
            continue
        result.append(a)
    return result


def save_title(title: str, url: str = "") -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    data: list[dict] = []
    if HISTORY_FILE.exists():
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = []
    today = date.today().isoformat()
    today_entry = next((e for e in data if e.get("date") == today), None)
    if today_entry:
        today_entry.setdefault("titles", []).append(title)
        if url:
            today_entry.setdefault("urls", []).append(url)
    else:
        entry: dict = {"date": today, "titles": [title]}
        if url:
            entry["urls"] = [url]
        data.append(entry)
    cutoff = (date.today() - timedelta(days=HISTORY_DAYS * 2)).isoformat()
    data = [e for e in data if e.get("date", "") >= cutoff]
    HISTORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
