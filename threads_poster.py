"""Threads API 포스팅 모듈 — 텍스트 + 분석 대댓글 + 이미지/링크 대댓글."""

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


def _create_text_container(client, user_id, access_token, text, reply_to_id=""):
    params = {
        "media_type": "TEXT",
        "text": text,
        "access_token": access_token,
    }
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    response = client.post(f"{GRAPH_API_BASE}/{user_id}/threads", params=params)
    if response.status_code >= 400:
        raise RuntimeError(f"create text container failed: {response.status_code} {response.text[:500]}")
    return response.json()["id"]


def _create_image_container(client, user_id, access_token, image_url, text="", reply_to_id=""):
    """이미지 컨테이너 생성 (텍스트 포함 가능)."""
    params = {
        "media_type": "IMAGE",
        "image_url": image_url,
        "access_token": access_token,
    }
    if text:
        params["text"] = text
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    response = client.post(f"{GRAPH_API_BASE}/{user_id}/threads", params=params)
    if response.status_code >= 400:
        raise RuntimeError(f"create image container failed: {response.status_code} {response.text[:500]}")
    return response.json()["id"]


def _publish(client, user_id, access_token, creation_id):
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


def post_thread(access_token, user_id, main_text, analysis_text=None,
                reply_text=None, image_url=None, source_link=None):
    """Threads 포스팅: 메인 → 분석 대댓글 → 첫 댓글 → 이미지+링크 대댓글.

    Returns:
        {"post_id": str, "analysis_id": str|None, "reply_id": str|None, "link_id": str|None}
    """
    with httpx.Client(timeout=30.0) as client:
        # 1. 메인 포스트
        main_cid = _create_text_container(client, user_id, access_token, main_text)
        time.sleep(CONTAINER_WAIT_DELAY)
        post_id = _publish(client, user_id, access_token, main_cid)
        print(f"  메인 포스트: {post_id}")

        # 2. 분석 대댓글
        analysis_id = None
        if analysis_text:
            time.sleep(FIRST_REPLY_DELAY)
            analysis_cid = _create_text_container(
                client, user_id, access_token, analysis_text, reply_to_id=post_id,
            )
            time.sleep(CONTAINER_WAIT_DELAY)
            analysis_id = _publish(client, user_id, access_token, analysis_cid)
            print(f"  분석 대댓글: {analysis_id}")

        # 3. 첫 댓글 (가벼운 부연)
        reply_id = None
        if reply_text:
            time.sleep(FIRST_REPLY_DELAY)
            reply_cid = _create_text_container(
                client, user_id, access_token, reply_text, reply_to_id=post_id,
            )
            time.sleep(CONTAINER_WAIT_DELAY)
            reply_id = _publish(client, user_id, access_token, reply_cid)
            print(f"  첫 댓글: {reply_id}")

        # 4. 이미지 + 원문 링크 대댓글
        link_id = None
        if image_url or source_link:
            time.sleep(FIRST_REPLY_DELAY)
            link_text = f"원문: {source_link}" if source_link else ""
            try:
                if image_url:
                    link_cid = _create_image_container(
                        client, user_id, access_token, image_url,
                        text=link_text, reply_to_id=post_id,
                    )
                else:
                    link_cid = _create_text_container(
                        client, user_id, access_token, link_text, reply_to_id=post_id,
                    )
                time.sleep(CONTAINER_WAIT_DELAY)
                link_id = _publish(client, user_id, access_token, link_cid)
                print(f"  링크 대댓글: {link_id}")
            except Exception as e:
                print(f"  링크 대댓글 실패 (건너뜀): {e}")

    return {
        "post_id": post_id,
        "analysis_id": analysis_id,
        "reply_id": reply_id,
        "link_id": link_id,
    }
