from news_filter import filter_by_keywords

def test_matches_title_keyword():
    articles = [
        {"title": "New GPT-5 model released", "summary": "Details about release"},
        {"title": "Best pizza recipes", "summary": "How to make pizza"},
    ]
    result = filter_by_keywords(articles)
    assert len(result) == 1
    assert "GPT" in result[0]["title"]

def test_matches_summary_keyword():
    articles = [
        {"title": "Tech update", "summary": "New artificial intelligence breakthrough"},
    ]
    result = filter_by_keywords(articles)
    assert len(result) == 1

def test_case_insensitive():
    articles = [
        {"title": "machine learning advances", "summary": "details"},
    ]
    result = filter_by_keywords(articles)
    assert len(result) == 1

def test_korean_keyword_match():
    articles = [
        {"title": "인공지능 기술 동향", "summary": "최신 트렌드"},
    ]
    result = filter_by_keywords(articles)
    assert len(result) == 1

def test_no_match_returns_empty():
    articles = [
        {"title": "Weather forecast", "summary": "Rain tomorrow"},
    ]
    result = filter_by_keywords(articles)
    assert len(result) == 0

def test_max_count_limits_results():
    articles = [
        {"title": f"AI news {i}", "summary": "AI content"} for i in range(20)
    ]
    result = filter_by_keywords(articles, max_count=10)
    assert len(result) == 10
