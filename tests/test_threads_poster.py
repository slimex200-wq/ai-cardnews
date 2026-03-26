"""threads_text_poster 모듈 테스트."""

import json
from unittest.mock import MagicMock, patch

import pytest

from threads_text_poster import (
    GRAPH_API_BASE,
    _is_retryable,
    check_url_accessible,
    create_carousel_reply_container,
    create_image_container,
    create_text_container,
    publish_container,
    post_hybrid,
)


def _mock_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text or json.dumps(json_data or {})
    return resp


class TestIsRetryable:
    def test_media_not_found_returns_true(self):
        resp = _mock_response(
            400,
            json_data={
                "error": {
                    "code": 24,
                    "error_subcode": 4279009,
                    "error_user_title": "Media Not Found",
                }
            },
        )
        assert _is_retryable(resp) is True

    def test_other_400_returns_false(self):
        resp = _mock_response(400, json_data={"error": {"code": 100}})
        assert _is_retryable(resp) is False

    def test_500_returns_true(self):
        resp = _mock_response(500)
        assert _is_retryable(resp) is True

    def test_200_returns_false(self):
        resp = _mock_response(200)
        assert _is_retryable(resp) is False


class TestCreateImageContainer:
    def test_success(self):
        client = MagicMock()
        client.post.return_value = _mock_response(200, {"id": "img_123"})

        result = create_image_container(client, "user1", "token1", "https://example.com/img.png")
        assert result == "img_123"

        call_args = client.post.call_args
        assert f"{GRAPH_API_BASE}/user1/threads" in call_args[0]
        assert call_args[1]["params"]["media_type"] == "IMAGE"
        assert call_args[1]["params"]["image_url"] == "https://example.com/img.png"

    def test_failure_raises(self):
        client = MagicMock()
        client.post.return_value = _mock_response(400, text="error")

        with pytest.raises(RuntimeError):
            create_image_container(client, "user1", "token1", "https://example.com/img.png")


class TestCreateTextContainer:
    def test_reply(self):
        client = MagicMock()
        client.post.return_value = _mock_response(200, {"id": "txt_789"})

        result = create_text_container(
            client, "user1", "token1", "reply text", reply_to_id="post_123"
        )
        assert result == "txt_789"

        call_args = client.post.call_args
        assert call_args[1]["params"]["media_type"] == "TEXT"
        assert call_args[1]["params"]["reply_to_id"] == "post_123"

    def test_standalone_post_no_reply_to_id(self):
        client = MagicMock()
        client.post.return_value = _mock_response(200, {"id": "txt_100"})

        result = create_text_container(client, "user1", "token1", "caption text")
        assert result == "txt_100"

        call_args = client.post.call_args
        assert "reply_to_id" not in call_args[1]["params"]


class TestCreateCarouselReplyContainer:
    def test_success(self):
        client = MagicMock()
        client.post.return_value = _mock_response(200, {"id": "car_456"})

        result = create_carousel_reply_container(
            client, "user1", "token1", ["img_1", "img_2"], reply_to_id="post_123"
        )
        assert result == "car_456"

        call_args = client.post.call_args
        assert call_args[1]["params"]["media_type"] == "CAROUSEL"
        assert call_args[1]["params"]["children"] == "img_1,img_2"
        assert call_args[1]["params"]["reply_to_id"] == "post_123"


class TestPublishContainer:
    def test_success_first_attempt(self):
        client = MagicMock()
        client.post.return_value = _mock_response(200, {"id": "pub_001"})

        result = publish_container(client, "user1", "token1", "creation_123")
        assert result == "pub_001"
        assert client.post.call_count == 1

    @patch("threads_text_poster.time.sleep")
    def test_retry_on_media_not_found(self, mock_sleep):
        client = MagicMock()
        fail_resp = _mock_response(
            400,
            json_data={"error": {"code": 24, "error_subcode": 4279009}},
        )
        success_resp = _mock_response(200, {"id": "pub_002"})
        client.post.side_effect = [fail_resp, fail_resp, success_resp]

        result = publish_container(client, "user1", "token1", "creation_123")
        assert result == "pub_002"
        assert client.post.call_count == 3
        assert mock_sleep.call_count == 2

    def test_non_retryable_error_raises_immediately(self):
        client = MagicMock()
        client.post.return_value = _mock_response(403, text="forbidden")

        with pytest.raises(RuntimeError, match="forbidden"):
            publish_container(client, "user1", "token1", "creation_123")
        assert client.post.call_count == 1


class TestCheckUrlAccessible:
    @patch("threads_text_poster.httpx.head")
    def test_accessible(self, mock_head):
        mock_head.return_value = _mock_response(200)
        assert check_url_accessible("https://example.com/img.png") is True

    @patch("threads_text_poster.httpx.head")
    def test_not_found(self, mock_head):
        mock_head.return_value = _mock_response(404)
        assert check_url_accessible("https://example.com/img.png") is False

    @patch("threads_text_poster.httpx.head")
    def test_network_error(self, mock_head):
        mock_head.side_effect = Exception("timeout")
        assert check_url_accessible("https://example.com/img.png") is False


class TestPostHybrid:
    @patch("threads_text_poster.time.sleep")
    @patch("threads_text_poster.httpx.Client")
    def test_text_only_flow(self, mock_client_cls, mock_sleep):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        # main container → publish main → reply container → publish reply
        mock_client.post.side_effect = [
            _mock_response(200, {"id": "main_c"}),
            _mock_response(200, {"id": "post_1"}),
            _mock_response(200, {"id": "reply_c"}),
            _mock_response(200, {"id": "reply_1"}),
        ]

        result = post_hybrid(
            access_token="token",
            user_id="user1",
            main_text="main text",
            reply_text="reply text",
            carousel_image_urls=None,
        )

        assert result["post_id"] == "post_1"
        assert result["reply_id"] == "reply_1"
        assert result["carousel_id"] is None
        assert mock_client.post.call_count == 4
