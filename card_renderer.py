import shutil
import os
from html2image import Html2Image
from pathlib import Path
from config import CARD_WIDTH, CARD_HEIGHT
from font_css import get_font_css


def _find_chrome():
    """크로스플랫폼 Chrome 경로 탐색"""
    env_path = os.environ.get("CHROME_BIN")
    if env_path:
        return env_path
    win_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if Path(win_path).exists():
        return win_path
    for name in ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]:
        found = shutil.which(name)
        if found:
            return found
    return None


chrome_path = _find_chrome()
hti_kwargs = {"size": (CARD_WIDTH, CARD_HEIGHT)}
if chrome_path:
    hti_kwargs["browser_executable"] = chrome_path

hti = Html2Image(**hti_kwargs)

COMMON_CSS = get_font_css() + """
* { margin:0; padding:0; box-sizing:border-box; }
body {
    width: 1080px; height: 1080px;
    font-family: 'Pretendard', 'Noto Sans CJK KR', 'Noto Sans KR', 'Malgun Gothic', sans-serif;
    overflow: hidden;
    -webkit-font-smoothing: antialiased;
}
"""


def _render(html, css, filename, output_dir):
    # Write full HTML file with embedded CSS (handles large base64 fonts)
    hti.output_path = str(output_dir)
    hti.screenshot(html_str=html, css_str=css, save_as=filename)
    return str(output_dir / filename)


def render_cover(title, date_str, output_dir, total_cards=4, keywords=None):
    css = COMMON_CSS + """
body {
    background: #0a0a0a;
    color: #fff;
    display: flex;
    flex-direction: column;
    padding: 100px;
    padding-top: 280px;
    position: relative;
}
.glow {
    position: absolute;
    top: -120px; left: 50%; transform: translateX(-50%);
    width: 500px; height: 400px;
    background: radial-gradient(ellipse, rgba(255,255,255,0.04) 0%, transparent 70%);
    pointer-events: none;
}
.border {
    position: absolute; inset: 0;
    border: 1px solid #2a2a2a;
    pointer-events: none;
}
.label {
    font-size: 22px; font-weight: 600;
    letter-spacing: 5px; color: #888;
    margin-bottom: 28px;
}
.title {
    font-size: 110px; font-weight: 900;
    line-height: 1.05; letter-spacing: -4px;
    margin-bottom: 20px;
}
.sep {
    width: 50px; height: 1px;
    background: #444; margin-bottom: 20px;
}
.date {
    font-size: 28px; color: #666; font-weight: 500;
}
.bottom {
    margin-top: auto;
    display: flex; justify-content: space-between; align-items: center;
}
.bottom-text { font-size: 24px; color: #555; }
.arrow-circle {
    width: 40px; height: 40px;
    border: 1px solid #444; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; color: #888;
}
.keywords {
    display: flex; gap: 12px; flex-wrap: wrap;
    margin-top: 32px;
}
.keyword {
    font-size: 20px; color: #999;
    padding: 8px 18px;
    border: 1px solid #333;
    border-radius: 20px;
}
"""
    keywords_html = ""
    if keywords:
        tags = "".join(f'<span class="keyword">#{k}</span>' for k in keywords)
        keywords_html = f'<div class="keywords">{tags}</div>'

    html = f"""
<div class="glow"></div>
<div class="border"></div>
<div class="label">AI WEEKLY</div>
<div class="title">이번 주<br>AI 뉴스</div>
<div class="sep"></div>
<div class="date">{date_str}</div>
{keywords_html}
<div class="bottom">
    <span class="bottom-text">{total_cards}편의 뉴스</span>
    <div class="arrow-circle">↓</div>
</div>
"""
    return _render(html, css, "card-01.png", output_dir)


def render_news_card(card_data, card_number, output_dir, total_cards=4):
    import re as _re

    num = card_data.get("number", card_number - 1)
    source = card_data.get("source", "")
    title = card_data.get("title", "")
    subtitle = card_data.get("subtitle", "")
    points = card_data.get("points", [])
    insight = card_data.get("insight", "")
    link = card_data.get("link", "")

    thumbnail_b64 = card_data.get("thumbnail_b64")
    thumbnail_html = ""
    if thumbnail_b64:
        thumbnail_html = f'<img class="thumbnail" src="data:image/png;base64,{thumbnail_b64}">'

    points_html = ""
    for p in points:
        points_html += f"""
        <div class="point">
            <div class="dot"></div>
            <span>{p}</span>
        </div>"""

    # 에디터 인사이트
    insight_html = ""
    if insight:
        insight_html = f"""
        <div class="insight">
            <span class="insight-label">INSIGHT</span>
            <span class="insight-text">{insight}</span>
        </div>"""

    # 원문 링크 (도메인만 표시)
    link_html = ""
    if link:
        domain = _re.sub(r'^https?://(www\.)?', '', link).split('/')[0]
        link_html = f'<div class="source-link">🔗 {domain}</div>'

    # page dots
    total_pages = total_cards + 2
    dots_html = ""
    for i in range(total_pages):
        if i == card_number - 1:
            dots_html += '<div class="dot-active"></div>'
        else:
            dots_html += '<div class="dot-inactive"></div>'

    css = COMMON_CSS + """
body {
    background: #0a0a0a;
    color: #fff;
    padding: 80px;
    position: relative;
    display: flex;
    flex-direction: column;
}
.border {
    position: absolute; inset: 0;
    border: 1px solid #2a2a2a;
    pointer-events: none;
}
.top-line {
    position: absolute; top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, #444, transparent);
}
.header {
    display: flex; justify-content: space-between; align-items: flex-start;
    margin-bottom: 36px;
}
.header-left {
    display: flex; flex-direction: column; gap: 4px;
}
.header-num {
    font-size: 20px; color: #888;
    font-weight: 600; letter-spacing: 2px;
}
.header-source {
    font-size: 20px; color: #666; font-weight: 500;
}
.thumbnail {
    width: 180px; height: 180px;
    border-radius: 16px;
    object-fit: cover;
}
.title {
    font-size: 62px; font-weight: 900;
    line-height: 1.15; letter-spacing: -2px;
    margin-bottom: 10px;
    word-break: keep-all;
    overflow-wrap: break-word;
}
.subtitle {
    font-size: 26px; color: #777;
    margin-bottom: 28px; font-weight: 400;
}
.sep {
    width: 100%; height: 1px;
    background: #222; margin-bottom: 24px;
}
.points {
    display: flex; flex-direction: column;
    gap: 14px;
}
.point {
    display: flex; align-items: flex-start; gap: 14px;
}
.point .dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: #fff; flex-shrink: 0;
    margin-top: 10px;
}
.point span {
    color: #bbb; font-size: 25px; line-height: 1.4;
}
.insight {
    margin-top: 20px; padding: 16px 20px;
    background: #141414;
    border-left: 3px solid #444;
    border-radius: 0 8px 8px 0;
    display: flex; align-items: center; gap: 12px;
}
.insight-label {
    font-size: 14px; font-weight: 700;
    color: #666; letter-spacing: 2px;
    flex-shrink: 0;
}
.insight-text {
    font-size: 22px; color: #999;
    font-style: italic;
}
.source-link {
    font-size: 18px; color: #555;
    margin-top: 12px;
}
.footer {
    margin-top: auto;
    display: flex; justify-content: space-between; align-items: center;
    padding-top: 16px;
}
.page-dots {
    display: flex; gap: 8px;
}
.dot-active {
    width: 22px; height: 8px;
    border-radius: 4px; background: #fff;
}
.dot-inactive {
    width: 8px; height: 8px;
    border-radius: 50%; background: #333;
}
"""
    html = f"""
<div class="border"></div>
<div class="top-line"></div>
<div class="header">
    <div class="header-left">
        <span class="header-num">{num:02d} / {total_cards:02d}</span>
        <span class="header-source">{source}</span>
    </div>
    {thumbnail_html}
</div>
<div class="title">{title}</div>
<div class="subtitle">{subtitle}</div>
<div class="sep"></div>
<div class="points">{points_html}</div>
{insight_html}
<div class="footer">
    {link_html}
    <div class="page-dots">{dots_html}</div>
</div>
"""
    return _render(html, css, f"card-{card_number:02d}.png", output_dir)


def render_closing(message, card_number, output_dir, total_cards=4):
    css = COMMON_CSS + """
body {
    background: #0a0a0a;
    color: #fff;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    position: relative;
}
.border {
    position: absolute; inset: 0;
    border: 1px solid #2a2a2a;
    pointer-events: none;
}
.glow {
    position: absolute;
    top: 50%; left: 50%; transform: translate(-50%, -50%);
    width: 450px; height: 450px;
    background: radial-gradient(circle, rgba(255,255,255,0.03) 0%, transparent 70%);
    pointer-events: none;
}
.message {
    font-size: 72px; font-weight: 900;
    letter-spacing: -2px;
    margin-bottom: 20px;
}
.sep {
    width: 50px; height: 1px;
    background: #333; margin-bottom: 24px;
}
.brand {
    font-size: 24px; color: #444;
    margin-bottom: 48px;
}
.cta {
    display: flex; flex-direction: column;
    gap: 14px; align-items: center;
}
.cta-item {
    font-size: 22px; color: #666;
    letter-spacing: 1px;
}
.cta-highlight {
    font-size: 24px; color: #999;
    font-weight: 600;
    padding: 12px 32px;
    border: 1px solid #333;
    border-radius: 28px;
    margin-top: 8px;
}
"""
    html = f"""
<div class="border"></div>
<div class="glow"></div>
<div class="message">{message}</div>
<div class="sep"></div>
<div class="brand">AI Weekly</div>
<div class="cta">
    <span class="cta-item">매일 AI 뉴스를 카드로 받아보세요</span>
    <span class="cta-highlight">팔로우 &amp; 저장</span>
</div>
"""
    return _render(html, css, f"card-{card_number:02d}.png", output_dir)
