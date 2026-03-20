import os
from pathlib import Path
from datetime import date

# RSS 소스
RSS_FEEDS = [
    # 영문
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://www.technologyreview.com/feed/",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "https://openai.com/blog/rss.xml",
    "https://blog.google/technology/ai/rss/",
    "https://huggingface.co/blog/feed.xml",
    # 한국어
    "https://www.aitimes.com/rss/allArticle.xml",
    "https://zdnet.co.kr/rss/ai_news.xml",
]

# Claude API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"

# 카드 디자인 — Vercel Dark + High Contrast
CARD_WIDTH = 1080
CARD_HEIGHT = 1080
BG_COLOR = "#0A0A0A"
TEXT_COLOR = "#FFFFFF"
ACCENT_COLOR = "#FFFFFF"
SUB_TEXT_COLOR = "#888888"
MUTED_COLOR = "#666666"
BORDER_COLOR = "#2A2A2A"
SEPARATOR_COLOR = "#222222"
POINT_TEXT_COLOR = "#BBBBBB"
FONT_PATH = "C:/Windows/Fonts/malgunbd.ttf"
FONT_PATH_REGULAR = "C:/Windows/Fonts/malgun.ttf"

# 출력
DEFAULT_OUTPUT = Path.home() / "Desktop" / "ai-cardnews"
DEFAULT_COUNT = 4

# AI 키워드 필터링
AI_KEYWORDS = [
    # 영문
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "neural network", "llm", "large language model", "gpt", "claude",
    "gemini", "chatbot", "generative ai", "transformer", "diffusion",
    "reinforcement learning", "computer vision", "nlp",
    "natural language processing", "openai", "anthropic", "hugging face",
    # 한국어
    "인공지능", "머신러닝", "딥러닝", "생성형", "대규모 언어 모델",
    "챗봇", "자연어 처리", "컴퓨터 비전", "강화학습",
]

# Unsplash API (썸네일 폴백)
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")

def get_output_dir(custom_path=None):
    base = Path(custom_path) if custom_path else DEFAULT_OUTPUT
    today = date.today().isoformat()
    output = base / today
    output.mkdir(parents=True, exist_ok=True)
    return output
