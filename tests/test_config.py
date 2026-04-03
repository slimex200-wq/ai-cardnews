import os


def test_content_mode_default():
    """CONTENT_MODE 미설정 시 informational."""
    os.environ.pop("CONTENT_MODE", None)
    import importlib
    import config
    importlib.reload(config)
    assert config.CONTENT_MODE == "informational"


def test_content_mode_from_env():
    """CONTENT_MODE 환경변수 반영."""
    os.environ["CONTENT_MODE"] = "viral"
    import importlib
    import config
    importlib.reload(config)
    assert config.CONTENT_MODE == "viral"
    os.environ.pop("CONTENT_MODE")


def test_pipeline_timeout_exists():
    from config import PIPELINE_TIMEOUT, API_MAX_RETRIES, API_RETRY_DELAY
    assert PIPELINE_TIMEOUT == 300
    assert API_MAX_RETRIES == 3
    assert API_RETRY_DELAY == 5
