from engagement_tracker import analyze_patterns


def _make_history() -> list[dict]:
    return [
        {"date": "2026-04-01", "mode": "viral", "score": 100, "views": 500, "likes": 10, "replies": 5, "reposts": 2, "quotes": 0, "title": "v1", "post_main": "viral1"},
        {"date": "2026-04-02", "mode": "informational", "score": 80, "views": 300, "likes": 8, "replies": 3, "reposts": 1, "quotes": 0, "title": "i1", "post_main": "info1"},
        {"date": "2026-04-03", "mode": "viral", "score": 90, "views": 400, "likes": 9, "replies": 4, "reposts": 1, "quotes": 0, "title": "v2", "post_main": "viral2"},
        {"date": "2026-03-30", "mode": "informational", "score": 70, "views": 200, "likes": 5, "replies": 2, "reposts": 0, "quotes": 0, "title": "i2", "post_main": "info2"},
        {"date": "2026-03-29", "mode": "informational", "score": 60, "views": 150, "likes": 3, "replies": 1, "reposts": 0, "quotes": 0, "title": "i3", "post_main": "info3"},
        {"date": "2026-03-28", "mode": "viral", "score": 50, "views": 100, "likes": 2, "replies": 1, "reposts": 0, "quotes": 0, "title": "v3", "post_main": "viral3"},
    ]


def test_analyze_patterns_filters_by_mode() -> None:
    history = _make_history()
    result = analyze_patterns(history, mode="informational")
    assert result is not None
    for entry in result["top"]:
        assert entry["mode"] == "informational"


def test_analyze_patterns_no_mode_uses_all() -> None:
    history = _make_history()
    result = analyze_patterns(history, mode=None)
    assert result is not None
    assert len([e for e in result["top"] if e["mode"] == "viral"]) > 0


def test_analyze_patterns_insufficient_data() -> None:
    history = [
        {"date": "2026-04-01", "mode": "informational", "score": 80, "views": 300, "likes": 8, "replies": 3, "reposts": 1, "quotes": 0, "title": "i1", "post_main": "info1"},
        {"date": "2026-04-02", "mode": "informational", "score": 70, "views": 200, "likes": 5, "replies": 2, "reposts": 0, "quotes": 0, "title": "i2", "post_main": "info2"},
    ]
    result = analyze_patterns(history, mode="informational")
    assert result is None
