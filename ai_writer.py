"""Threads 바이럴 텍스트 포스트 생성 모듈.

8개 소스에서 수집한 기사 중 가장 바이럴 가능성 높은 1개를 골라
Threads 텍스트 포스트 + 첫 댓글을 생성.
"""

import json
import re

import anthropic
from config import ANTHROPIC_API_KEY, MODEL


def build_prompt(articles, used_titles=None):
    """Threads 바이럴 텍스트 포스트 프롬프트."""
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

### post_analysis: 분석 대댓글 (150~250자)
메인 포스트의 대댓글로 다는 심층 분석. 3단 구조로 작성:
1. **무슨 의미인지** (1~2줄): 이 뉴스가 뭘 뜻하는지 쉽게 풀어 설명
2. **왜 중요한지** (1~2줄): 업계/개발자/일반인에게 미치는 영향
3. **우리는 뭘 해야 하는지** (1줄): 구체적 행동 제안 또는 관점 제시
- 톤: 메인보다 약간 진지하게, ~합니다/~입니다 존댓말 위주
- "무슨 의미인지:", "왜 중요한지:", "뭘 해야 하는지:" 같은 라벨 붙이지 말 것 — 자연스럽게 이어 쓸 것

### post_reply: 본인 첫 댓글 (50~120자)
메인 포스트에 본인이 다는 첫 댓글. 가벼운 부연 의견 또는 추가 맥락.
- 대화 시작점 역할 (알고리즘에 초기 인게이지먼트 신호)
- 매번 다른 시작 패턴 사용할 것. "개인적으로"로 시작 금지.
- 좋은 시작 패턴 예시 (매번 다르게):
  - 반전/추가 정보: "근데 진짜 웃긴 건 이 회사가 작년에는..."
  - 경험 공유: "나도 써봤는데 솔직히..."
  - 도발적 의견: "ㄹㅇ 이러다 3년 안에..."
  - 비교/대조: "구글은 이미 이거 포기했는데..."
- 나쁜 예: "원문 링크: https://..." (링크 댓글은 도달률 킬러)
- 나쁜 예: "개인적으로는..." (반복되면 봇처럼 보임)

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
    "link": "선택한 기사의 Link 필드 그대로 복사",
    "reason": "이 기사를 선택한 이유 (내부 참고용)"
  }},
  "post_main": "메인 포스트 텍스트 (200~350자)",
  "post_analysis": "분석 대댓글 (150~250자, 의미/중요성/행동)",
  "post_reply": "본인 첫 댓글 (50~120자)",
  "topic_tag": "AI 뉴스"
}}

기사들:
{articles_text}"""


def _format_articles(articles):
    text = ""
    for i, a in enumerate(articles, 1):
        text += f"\n### Article {i}\n"
        text += f"Title: {a['title']}\n"
        text += f"Summary: {a['summary']}\n"
        text += f"Source: {a['source']}\n"
        text += f"Link: {a.get('link', '')}\n"
    return text


def _build_history_instruction(used_titles):
    if not used_titles:
        return ""
    titles_list = "\n".join(f"- {t}" for t in used_titles[:12])
    return f"""
## 중복 방지 (필수)
아래는 최근 며칠간 이미 다룬 기사 제목입니다. **같은 주제, 같은 사건, 같은 인물/회사에 대한 기사는 반드시 제외**해주세요.
URL이 다르더라도 동일한 이벤트를 다룬 기사는 중복입니다.
{titles_list}
"""


def _parse_response(text):
    text = text.strip()
    code_block = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if code_block:
        text = code_block.group(1).strip()
    else:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
    return json.loads(text)


def generate_post(articles, used_titles=None):
    """Threads 텍스트 포스트 생성."""
    prompt = build_prompt(articles, used_titles)
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = message.content[0].text
    try:
        return _parse_response(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[경고] JSON 파싱 실패, 재시도 중... ({e})")
        message = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response_text},
                {"role": "user", "content": "JSON 형식이 올바르지 않습니다. 올바른 JSON으로 다시 응답해주세요."},
            ],
        )
        return _parse_response(message.content[0].text)
