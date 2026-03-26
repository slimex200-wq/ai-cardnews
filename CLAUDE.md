# AI Threads

## Commands
- `python main.py` - 수집 → 생성 → Threads 포스팅
- `python main.py --dry-run` - 포스팅 없이 생성만

## Architecture
8개 소스 병렬 수집 → AI 키워드 필터 → Claude API 바이럴 포스트 생성 → Threads 포스팅

| 파일 | 역할 |
|------|------|
| main.py | 메인 파이프라인 |
| social_collector.py | 8개 소스 병렬 수집 (last30days 스킬 활용) |
| ai_writer.py | Claude API 바이럴 포스트 생성 |
| threads_poster.py | Threads Graph API 텍스트 포스트 + 첫 댓글 |
| rss_collector.py | RSS 피드 수집 (보충용) |
| news_filter.py | AI 키워드 필터링 |
| history.py | 중복 방지 히스토리 |
| telegram_notify.py | 텔레그램 프리뷰/결과 알림 |
| config.py | 환경변수, 모델, 키워드 설정 |

## 수집 소스 (social_collector.py)
| 소스 | API | 키 |
|------|-----|-----|
| Reddit | ScrapeCreators | SCRAPECREATORS_API_KEY |
| Hacker News | Algolia | 불필요 |
| YouTube | yt-dlp | 불필요 |
| TikTok | ScrapeCreators | SCRAPECREATORS_API_KEY |
| Instagram | ScrapeCreators | SCRAPECREATORS_API_KEY |
| Bluesky | AT Protocol | BSKY_HANDLE + BSKY_APP_PASSWORD |
| Truth Social | Mastodon API | TRUTHSOCIAL_TOKEN |
| Polymarket | Gamma API | 불필요 |

## Conventions
- output/{날짜}/post.json에 생성 결과 저장
- output/history.json으로 최근 3일 기사 중복 방지
- Claude 모델: claude-sonnet-4-20250514

## NEVER
- NEVER 해시태그(#) 사용 -- Threads가 스팸 처리
- NEVER 외부 링크 포함 -- 도달률 킬러
- NEVER "개인적으로"로 첫 댓글 시작 -- 반복되면 봇처럼 보임
- NEVER output/ 내 생성된 파일을 수동 편집 -- CI가 매일 자동 덮어씀
