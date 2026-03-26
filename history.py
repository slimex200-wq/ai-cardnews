"""포스팅 히스토리 관리 — 중복 방지."""

import json
from datetime import date, timedelta
from pathlib import Path

HISTORY_DAYS = 3
HISTORY_FILE = Path("output/history.json")


def load_used_titles():
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError):
        return []
    cutoff = (date.today() - timedelta(days=HISTORY_DAYS)).isoformat()
    titles = []
    for entry in data:
        if entry.get("date", "") >= cutoff:
            titles.extend(entry.get("titles", []))
    return titles


def save_title(title):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = []
    if HISTORY_FILE.exists():
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = []
    today = date.today().isoformat()
    today_entry = next((e for e in data if e.get("date") == today), None)
    if today_entry:
        today_entry.setdefault("titles", []).append(title)
    else:
        data.append({"date": today, "titles": [title]})
    cutoff = (date.today() - timedelta(days=HISTORY_DAYS * 2)).isoformat()
    data = [e for e in data if e.get("date", "") >= cutoff]
    HISTORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
