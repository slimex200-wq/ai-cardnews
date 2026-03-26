"""AI 콘텐츠 생성 모듈 v2 — 카드뉴스 모드 + Threads 텍스트 모드 듀얼 지원.

Mode:
  - "card" (기본): 기존 카드뉴스 캐러셀 생성
  - "text": Threads 알고리즘 최적화 텍스트 포스트 생성
"""

import json
import re
from datetime import date
import anthropic
from config import ANTHROPIC_API_KEY, MODEL


# ─────────────────────────────────────────────
# 1. 기존 카드뉴스 모드 (변경 없음)
# ─────────────────────────────────────────────

def build_prompt_card(articles, select_count=None, used_titles=None):
    """기존 카드뉴스 프롬프트 (ai_writer.py 원본 그대로)"""
    articles_text = _format_articles(articles)

    selection_instruction = ""
    if select_count and len(articles) > select_count:
        selection_instruction = f"""
먼저 아래 {len(articles)}개 기사 중 가장 중요하고 흥미로운 {select_count}개를 선별해주세요.
선별 기준: AI 업계에 미치는 영향력, 독자 관심도, 정보의 신선도
선별된 {select_count}개 기사만 카드뉴스로 변환해주세요.
"""

    history_instruction = _build_history_instruction(used_titles)

    return f"""{selection_instruction}{history_instruction}당신은 AI/테크 업계 시니어 에디터입니다. 아래 기사들을 한국어 인스타그램 카드뉴스로 변환해주세요.
이 카드뉴스는 **AI Daily** — 매일 발행되는 일간 뉴스레터입니다.

## 톤 & 스타일
- 업계 전문가가 동료에게 브리핑하는 느낌
- 반드시 구체적 수치, 금액, 날짜, 인물명을 포함할 것
- "폭발적 증가", "절호의 기회" 같은 빈 수식어 금지
- "한 주", "이번 주", "this week" 등 주간 표현 절대 금지 — "오늘", "최근" 등 일간 표현만 사용
- 마지막 포인트는 반드시 "왜 중요한지" 분석 (So What)으로 마무리

## 각 기사에 대해:
- title: 임팩트 있는 제목 (15자 이내, 한국어)
- subtitle: 핵심 맥락 한 줄 (25자 이내, 한국어)
- points: 핵심 포인트 5개 (각 35자 이내, 한국어)
  - 1~3번째: 구체적 팩트 (수치, 인물, 날짜 포함)
  - 4번째: 업계 영향 또는 파급 효과
  - 5번째: "왜 주목해야 하는가" 에디터 관점 분석
- insight: 에디터 한줄평 (30자 이내, 독자에게 시사점)
- source: 출처명
- link: 원문 URL (기사의 Link 필드 그대로 사용)
- keywords: 이 기사의 핵심 키워드 1~2개 (표지에 사용)
- original_title: 원본 기사의 Title 필드를 그대로 복사 (이미지 매칭에 사용, 절대 수정 금지)

## 추가 생성 항목:
- cover_headline: 이번 회차의 핵심 트렌드를 담은 표지 헤드라인 (20자 이내, 한국어, 예: "AI가 제조업을 삼킨다")
- trend_summary: 선별된 기사들을 관통하는 공통 트렌드 한 문장 (40자 이내)
- caption: Threads 포스트용 텍스트. 아래 규칙을 반드시 따를 것:
  - 첫 1~2줄: 오늘 뉴스 중 가장 임팩트 있는 팩트로 시작 (호기심 유발, "더 보기" 전에 보이는 부분)
  - 중간: 오늘 다룬 주요 뉴스 2~3개를 "- " 불릿으로 한 줄씩 요약
  - 마무리: "자세한 내용은 카드뉴스로 정리했습니다 👇" 또는 유사한 이미지 유도 문구
  - 맨 끝: 주제 태그 1개만 (예: "AI 뉴스")
  - 해시태그(#) 절대 금지 — Threads는 해시태그 다수 사용을 스팸으로 인식
  - 톤: 전문가가 동료에게 브리핑하는 ~합니다/~입니다 존댓말
  - 이모지: 최대 1~2개 (👇, 🔥 정도), 과다 사용 금지
  - 총 300~450자 이내
  - 원문 링크 포함하지 말 것

JSON 형식으로 응답해주세요:
{{
  "cover_headline": "표지 헤드라인",
  "cover_date": "{date.today().isoformat()}",
  "trend_summary": "오늘의 AI 트렌드 한 줄 요약",
  "cards": [
    {{
      "number": 1, "original_title": "원문 기사 Title 그대로 복사",
      "title": "...",
      "subtitle": "...",
      "points": ["팩트1", "팩트2", "팩트3", "영향", "So What"],
      "insight": "에디터 한줄평",
      "source": "...",
      "link": "https://...",
      "keywords": ["키워드1"]
    }}
  ],
  "closing_message": "읽어주셔서 감사합니다",
  "caption": "첫줄 후킹\\n\\n- 뉴스1 요약\\n- 뉴스2 요약\\n\\n카드뉴스로 정리했습니다 👇\\n\\nAI 뉴스"
}}

기사들:
{articles_text}"""


# ─────────────────────────────────────────────
# 2. Threads 텍스트 포스트 모드 (NEW)
# ─────────────────────────────────────────────

def build_prompt_text(articles, used_titles=None):
    """Threads 알고리즘 최적화 텍스트 포스트 프롬프트.

    핵심 원칙:
    - 뉴스 1개만 픽 → 의견 + 질문으로 대화 유발
    - 캐러셀 없음, 텍스트 온리
    - 링크 없음 (도달률 킬러)
    - 댓글이 달릴 수밖에 없는 구조
    """
    articles_text = _format_articles(articles)
    history_instruction = _build_history_instruction(used_titles)

    return f"""{history_instruction}당신은 한국 AI/테크 커뮤니티에서 활동하는 인플루언서입니다.
아래 기사들 중 **가장 논쟁적이거나 흥미로운 1개**를 골라, Threads 텍스트 포스트를 작성하세요.

## 핵심 목표
**댓글이 달리는 포스트**를 만드는 것. 정보 전달이 아님.
Threads 알고리즘은 포스팅 후 30분 내 댓글(reply)을 가장 중요한 신호로 봄.

## 기사 선별 기준 (우선순위)
1. 의견이 갈릴 수 있는 뉴스 (찬반 논쟁 가능)
2. "진짜?" 하고 놀랄 만한 팩트가 있는 뉴스
3. 개발자/직장인이 공감할 수 있는 뉴스
4. 단순 제품 업데이트나 기능 추가보다는 업계 판도를 바꾸는 뉴스

## 포스트 구조 (반드시 이 순서로)

### post_main: 메인 포스트 (200~350자)
1. **첫 줄 (Hook)**: 놀라운 팩트 또는 도발적 의견으로 시작. "더 보기" 누르기 전에 보이는 2줄이 승부처.
   - 좋은 예: "메타가 인간 없이 AI가 스스로 진화하는 시스템을 만들었는데..."
   - 나쁜 예: "메타가 새로운 AI 기술을 발표했습니다."
2. **본문 (2~4줄)**: 핵심 팩트 1~2개 + 본인 의견/해석. 수치가 있으면 반드시 포함.
3. **마지막 줄 (질문)**: 반드시 독자에게 의견을 묻는 질문으로 끝낼 것.
   - 좋은 예: "너희는 이런 자율 AI, 긍정적으로 봐 아니면 무섭다고 봐?"
   - 좋은 예: "솔직히 이거 개발자한테 좋은 소식이야 나쁜 소식이야?"
   - 나쁜 예: "여러분의 생각은 어떠신가요?" (너무 딱딱함)

### post_reply: 본인 첫 댓글 (50~120자)
메인 포스트에 본인이 다는 첫 댓글. 추가 맥락이나 부연 의견.
- 대화 시작점 역할 (알고리즘에 초기 인게이지먼트 신호)
- 좋은 예: "개인적으로는 AI가 코딩까지 대체하면 나도 밥줄이 위험할 것 같은데 ㅋㅋ"
- 나쁜 예: "원문 링크: https://..." (링크 댓글은 도달률 킬러)

## 톤 & 스타일 규칙
- 반말 + 존댓말 자연스럽게 섞기 (한국 온라인 커뮤니티 톤)
- ~한다/~했다/~인듯 + 가끔 ~합니다 존댓말
- "ㅋㅋ", "ㄹㅇ", "솔직히" 같은 구어체 자연스럽게 사용 가능
- 이모지 1~2개 이하 (🤔, 🔥 정도)
- 해시태그(#) 절대 금지
- 맨 끝에 주제 태그 1개만 (예: "AI 뉴스")
- 외부 링크 절대 포함하지 말 것
- "카드뉴스", "자세한 내용은", "정리했습니다" 같은 표현 금지

## 금지 패턴 (이런 포스트는 조회수 0)
- 뉴스 요약 나열 (불릿 포인트로 여러 뉴스 나열)
- "~했습니다. ~했습니다." 반복되는 보도자료 톤
- 의견 없이 팩트만 전달
- 질문 없이 끝나는 포스트
- "여러분의 생각은?" 같은 형식적 질문

JSON 형식으로 응답:
{{
  "selected_article": {{
    "original_title": "선택한 기사의 Title 필드 그대로 복사",
    "reason": "이 기사를 선택한 이유 (내부 참고용)"
  }},
  "post_main": "메인 포스트 텍스트 (200~350자)",
  "post_reply": "본인 첫 댓글 (50~120자)",
  "topic_tag": "AI 뉴스"
}}

기사들:
{articles_text}"""


# ─────────────────────────────────────────────
# 공통 유틸
# ─────────────────────────────────────────────

def _format_articles(articles):
    """기사 목록을 프롬프트용 텍스트로 변환."""
    text = ""
    for i, a in enumerate(articles, 1):
        text += f"\n### Article {i}\n"
        text += f"Title: {a['title']}\n"
        text += f"Summary: {a['summary']}\n"
        if a.get('body'):
            text += f"Body (excerpt): {a['body']}\n"
        text += f"Source: {a['source']}\n"
        text += f"Link: {a.get('link', '')}\n"
    return text


def _build_history_instruction(used_titles):
    """중복 방지 지시문 생성."""
    if not used_titles:
        return ""
    titles_list = "\n".join(f"- {t}" for t in used_titles[:12])
    return f"""
## 중복 방지 (필수)
아래는 최근 며칠간 이미 다룬 기사 제목입니다. **같은 주제, 같은 사건, 같은 인물/회사에 대한 기사는 반드시 제외**해주세요.
URL이 다르더라도 동일한 이벤트(예: 같은 컨퍼런스, 같은 발표, 같은 사건)를 다룬 기사는 중복입니다.
{titles_list}
"""


def parse_response(text):
    """Claude 응답에서 JSON 추출."""
    text = text.strip()
    code_block = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if code_block:
        text = code_block.group(1).strip()
    else:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
    return json.loads(text)


def generate_card_content(articles, select_count=None, used_titles=None):
    """기존 카드뉴스 모드 (하위 호환)."""
    return _call_api(build_prompt_card(articles, select_count, used_titles))


def generate_text_post(articles, used_titles=None):
    """Threads 텍스트 포스트 모드 (NEW)."""
    return _call_api(build_prompt_text(articles, used_titles))


def _call_api(prompt):
    """Claude API 호출 + JSON 파싱."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = message.content[0].text
    try:
        return parse_response(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[경고] JSON 파싱 실패, 재시도 중... ({e})")
        message = client.messages.create(
            model=MODEL,
            max_tokens=3000,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response_text},
                {"role": "user", "content": "JSON 형식이 올바르지 않습니다. 올바른 JSON으로 다시 응답해주세요."},
            ],
        )
        return parse_response(message.content[0].text)
