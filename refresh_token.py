"""Threads long-lived token 자동 갱신.

Threads Graph API의 refresh_access_token 엔드포인트를 호출하여
기존 long-lived token을 새 long-lived token으로 교환합니다.
"""

import os
import sys
import json
import urllib.request
import urllib.error


GRAPH_BASE_URL = "https://graph.threads.net"


def refresh_token(current_token: str) -> dict:
    """현재 토큰으로 새 long-lived token을 발급받습니다."""
    params = urllib.parse.urlencode({
        "grant_type": "th_refresh_token",
        "access_token": current_token,
    })
    url = f"{GRAPH_BASE_URL}/refresh_access_token?{params}"

    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def check_token_validity(token: str) -> dict:
    """토큰 유효성 확인 (me 엔드포인트 호출)."""
    params = urllib.parse.urlencode({"fields": "id,username"})
    url = f"{GRAPH_BASE_URL}/me?{params}"

    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    current_token = os.environ.get("THREADS_ACCESS_TOKEN", "")
    if not current_token:
        print("ERROR: THREADS_ACCESS_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    # 1. 현재 토큰 유효성 확인
    try:
        profile = check_token_validity(current_token)
        print(f"현재 토큰 유효: @{profile.get('username', 'unknown')}")
    except urllib.error.HTTPError as e:
        print(f"ERROR: 현재 토큰 만료됨 (HTTP {e.code}). Meta 콘솔에서 수동 재발급 필요.", file=sys.stderr)
        sys.exit(2)

    # 2. 토큰 갱신
    try:
        result = refresh_token(current_token)
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"ERROR: 토큰 갱신 실패 (HTTP {e.code}): {body}", file=sys.stderr)
        sys.exit(1)

    new_token = result.get("access_token", "")
    expires_in = result.get("expires_in", 0)

    if not new_token:
        print(f"ERROR: 응답에 access_token 없음: {result}", file=sys.stderr)
        sys.exit(1)

    # 3. 새 토큰 유효성 확인
    try:
        profile = check_token_validity(new_token)
        print(f"새 토큰 유효: @{profile.get('username', 'unknown')}")
    except urllib.error.HTTPError as e:
        print(f"ERROR: 새 토큰 검증 실패 (HTTP {e.code})", file=sys.stderr)
        sys.exit(1)

    days = expires_in // 86400
    print(f"토큰 갱신 성공: {days}일 유효")

    # GitHub Actions output으로 새 토큰 전달
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"new_token={new_token}\n")
            f.write(f"expires_days={days}\n")
    else:
        # 로컬 실행 시 토큰 출력
        print(f"NEW_TOKEN={new_token}")


if __name__ == "__main__":
    main()
