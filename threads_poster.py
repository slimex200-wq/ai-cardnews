"""Threads API 포스팅 모듈 — 텍스트 포스트 + 첫 댓글."""

import time
import httpx

GRAPH_API_BASE = "https://graph.threads.net/v1.0"
PUBLISH_RETRY_ATTEMPTS = 5
PUBLISH_RETRY_DELAY = 3
CONTAINER_WAIT_DELAY = 2
FIRST_REPLY_DELAY = 5


def _is_retryable(response):
    if response.status_code >= 500:
        return True
    if response.status_code == 400:
        try:
            error = response.json().get("error", {})
        except Exception:
            return False
        return error.get("code") == 24 and error.get("error_subcode") == 4279009
    return False


def create_text_container(client, user_id, access_token, text, reply_to_id=""):
    params = {
        "media_type": "TEXT",
        "text": text,
        "access_token": access_token,
    }
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    response = client.post(f"{GRAPH_API_BASE}/{user_id}/threads", params=params)
    if response.status_code >= 400:
        raise RuntimeError(f"create container failed: {response.status_code} {response.text[:500]}")
    return response.json()["id"]


def publish_container(client, user_id, access_token, creation_id):
    response = None
    for attempt in range(1, PUBLISH_RETRY_ATTEMPTS + 1):
        response = client.post(
            f"{GRAPH_API_BASE}/{user_id}/threads_publish",
            params={"creation_id": creation_id, "access_token": access_token},
        )
        if response.status_code < 400:
            return response.json()["id"]
        if attempt < PUBLISH_RETRY_ATTEMPTS and _is_retryable(response):
            print(f"  발행 재시도 {attempt}/{PUBLISH_RETRY_ATTEMPTS}...")
            time.sleep(PUBLISH_RETRY_DELAY)
            continue
        break
    raise RuntimeError(f"publish failed: {response.status_code} {response.text[:500]}")


def post_text(access_token, user_id, main_text, reply_text=None):
    """텍스트 포스트 + 첫 댓글 발행."""
    with httpx.Client(timeout=30.0) as client:
        main_cid = create_text_container(client, user_id, access_token, main_text)
        time.sleep(CONTAINER_WAIT_DELAY)
        post_id = publish_container(client, user_id, access_token, main_cid)
        print(f"  메인 포스트: {post_id}")

        reply_id = None
        if reply_text:
            time.sleep(FIRST_REPLY_DELAY)
            reply_cid = create_text_container(
                client, user_id, access_token, reply_text, reply_to_id=post_id,
            )
            time.sleep(CONTAINER_WAIT_DELAY)
            reply_id = publish_container(client, user_id, access_token, reply_cid)
            print(f"  첫 댓글: {reply_id}")

    return {"post_id": post_id, "reply_id": reply_id}
