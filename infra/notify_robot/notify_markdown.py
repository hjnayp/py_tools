#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from typing import Any


DEFAULT_WEBHOOK_KEY = "54729f17-3a23-4614-aaec-364432f01e4b"
DEFAULT_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send"


def send_wecom_message(content: str, webhook_key: str = DEFAULT_WEBHOOK_KEY) -> dict[str, Any]:
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": content,
        },
    }

    url = f"{DEFAULT_WEBHOOK_URL}?key={webhook_key}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response_text = response.read().decode("utf-8")
            return json.loads(response_text)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace") if error.fp else str(error)
        raise RuntimeError(f"企业微信机器人请求失败（HTTP {error.code}）：{detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"企业微信机器人请求失败：{error.reason}") from error


def parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="发送企业微信机器人 Markdown 消息",
    )
    parser.add_argument("content", nargs="?", help="消息内容")
    parser.add_argument("--content", dest="content_opt", help="消息内容")
    parser.add_argument("--webhook-key", default=DEFAULT_WEBHOOK_KEY, help="机器人 webhook key")
    args = parser.parse_args()

    final_content = args.content_opt if args.content_opt is not None else args.content
    if not final_content:
        parser.error("缺少消息内容，请传入位置参数 content 或 --content")

    args.content = final_content
    return args


def main() -> int:
    args = parse_cli_args()
    result = send_wecom_message(content=args.content, webhook_key=args.webhook_key)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())