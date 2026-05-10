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


def test_notion_review_required_from_env():
    os.environ["NOTION_REVIEW_REQUIRED"] = "true"
    import importlib
    import config
    importlib.reload(config)
    assert config.NOTION_REVIEW_REQUIRED is True
    os.environ.pop("NOTION_REVIEW_REQUIRED")


def test_load_env_file_sets_missing_values(tmp_path):
    import config

    key = "AI_THREADS_TEST_ENV_FILE_VALUE"
    os.environ.pop(key, None)
    env_path = tmp_path / ".env"
    env_path.write_text(f"{key}=from-file\n", encoding="utf-8")

    config._load_env_file(str(env_path))

    assert os.environ[key] == "from-file"
    os.environ.pop(key, None)
