from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


# 生成公告数据的不可变结构
@dataclass(frozen=True)
class Notice:
    channel: str
    environment: str
    title: str
    author: str
    theme: str
    content: str

    def to_dict(self) -> Mapping[str, str]:
        return {
            "channel": self.channel,
            "environment": self.environment,
            "title": self.title,
            "author": self.author,
            "theme": self.theme,
            "content": self.content,
        }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_required(name: str, value: str) -> str:
    if value.strip() == "":
        raise ValueError(f"{name} 不能为空")
    return value


def validate_environment(value: str) -> str:
    allowed = ("test", "prod")
    if value not in allowed:
        raise ValueError(f"环境参数无效: {value}")
    return value


def build_notice(
        channel: str,
        environment: str,
        title: str,
        author: str,
        theme: str,
        content: str,
) -> Notice:
    return Notice(
        channel=channel,
        environment=environment,
        title=title,
        author=author,
        theme=theme,
        content=content,
    )


def ensure_output_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json_file(path: Path, data: Mapping[str, str]) -> Path:
    json_text = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(json_text, encoding="utf-8")
    return path


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成游戏公告 JSON")
    parser.add_argument("--channel", required=True, type=str, help="游戏渠道")
    parser.add_argument("--env", required=True, type=str, help="发布环境")
    parser.add_argument("--title", required=True, type=str, help="公告标题")
    parser.add_argument("--author", required=True, type=str, help="作者")
    parser.add_argument("--theme", default="", type=str, help="主题图片 URL")
    parser.add_argument("--content", required=True, type=str, help="公告内容")
    parser.add_argument("--output-dir", default=".", type=str, help="输出目录")
    parser.add_argument("--file-name", default="notice_update.json", type=str, help="文件名")
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)

    channel = validate_required("渠道", args.channel)
    env = validate_environment(validate_required("环境", args.env))
    title = validate_required("标题", args.title)
    author = validate_required("作者", args.author)
    content = validate_required("内容", args.content)

    notice = build_notice(
        channel=channel,
        environment=env,
        title=title,
        author=author,
        theme=args.theme,
        content=content,
    )

    output_dir = ensure_output_dir(Path(args.output_dir))
    output_path = output_dir / args.file_name

    written_path = write_json_file(output_path, notice.to_dict())

    print(f"JSON 已生成: {written_path}")
    print(json.dumps(notice.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
