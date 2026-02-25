from __future__ import annotations

import argparse
import base64
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

PYTHON_TOOLS_ROOT = Path(__file__).resolve().parents[2]
if str(PYTHON_TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_TOOLS_ROOT))

from infra.oss.upload_oss import upload_oss
from infra.notify_robot.notify_markdown import send_wecom_message

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


def resolve_output_dir(raw_output_dir: str) -> Path:
    output_dir = Path(raw_output_dir)
    if output_dir.is_absolute():
        return output_dir
    return Path(__file__).resolve().parent / output_dir


def write_json_file(path: Path, data: Mapping[str, str]) -> Path:
    json_text = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(json_text, encoding="utf-8")
    return path


def normalize_text_arg(value: str | list[str] | None) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(part for part in value if part is not None)
    return value


def normalize_content_arg(value: str | list[str] | None) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(part for part in value if part is not None)
    return value


def normalize_content_text(content: str) -> str:
    return (
        content
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("`r`n", "\n")
        .replace("`n", "\n")
        .replace("`r", "\n")
        .replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
    )


def resolve_content(args: argparse.Namespace) -> str:
    if args.content_base64:
        decoded = base64.b64decode(args.content_base64).decode("utf-8")
        return normalize_content_text(decoded)

    if args.content_file:
        content_file = Path(args.content_file).expanduser().resolve()
        if not content_file.exists():
            raise FileNotFoundError(f"content 文件不存在: {content_file}")
        return normalize_content_text(content_file.read_text(encoding="utf-8"))

    if args.content_stdin:
        return normalize_content_text(sys.stdin.read())

    return normalize_content_text(normalize_content_arg(args.content))


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成游戏公告 JSON")
    parser.add_argument("--channel", required=True, type=str, help="游戏渠道")
    parser.add_argument("--env", required=True, type=str, help="发布环境")
    parser.add_argument("--title", required=True, nargs="+", help="公告标题")
    parser.add_argument("--author", required=True, nargs="+", help="作者")
    parser.add_argument("--theme", default="", nargs="*", help="主题图片 URL")
    parser.add_argument("--content", nargs="+", help="公告内容")
    parser.add_argument("--content-base64", type=str, help="Base64 编码后的公告内容（支持稳定传多行）")
    parser.add_argument("--content-file", type=str, help="从文件读取公告内容（支持多行）")
    parser.add_argument("--content-stdin", action="store_true", help="从标准输入读取公告内容（支持多行）")
    parser.add_argument("--output-dir", default=".", type=str, help="输出目录（相对路径基于脚本目录）")
    parser.add_argument("--file-name", default="notice_update.json", type=str, help="文件名")
    args = parser.parse_args(argv)

    args.title = normalize_text_arg(args.title)
    args.author = normalize_text_arg(args.author)
    args.theme = normalize_text_arg(args.theme)

    has_content = bool(args.content)
    has_content_base64 = bool(args.content_base64)
    has_content_file = bool(args.content_file)
    has_content_stdin = bool(args.content_stdin)
    content_sources_count = sum([has_content, has_content_base64, has_content_file, has_content_stdin])
    if content_sources_count == 0:
        parser.error("缺少公告内容，请使用 --content / --content-base64 / --content-file / --content-stdin 之一")
    if content_sources_count > 1:
        parser.error("--content / --content-base64 / --content-file / --content-stdin 只能传一个")

    args.content = resolve_content(args)
    return args


def get_oss_upload_params(args: argparse.Namespace) -> tuple[str, str]:
    stage = "2" if args.env == "prod" else "1"
    channel = args.channel.strip()
    if channel == "":
        raise ValueError("渠道不能为空")

    return (stage, channel)


def upload_to_oss(args: argparse.Namespace, local_file: Path) -> None:
    stage, channel = get_oss_upload_params(args)
    result = upload_oss(
        source=local_file.resolve(),
        stage=stage,
        channel=channel,
        remote_subdir="notice/",
        force=True,
        update=True,
    )
    if result != 0:
        raise RuntimeError(f"上传失败，退出码: {result}")


def send_notify_markdown(content: str) -> None:
    """
    发送 Markdown 通知到企业微信机器人
    
    :param content: Markdown 格式的消息内容
    :raises RuntimeError: 当发送失败时抛出异常
    """
    result = send_wecom_message(content)
    if result.get("errcode") != 0:
        error_msg = result.get("errmsg", "未知错误")
        raise RuntimeError(f"发送企业微信通知失败: {error_msg}")


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

    output_dir = ensure_output_dir(resolve_output_dir(args.output_dir))
    output_path = output_dir / args.file_name

    written_path = write_json_file(output_path, notice.to_dict())

    print(f"JSON 已生成: {written_path}")
    print(json.dumps(notice.to_dict(), ensure_ascii=False, indent=2))
    upload_to_oss(args, written_path)
    notify_content = f"# 公告更新\n{json.dumps(notice.to_dict(), ensure_ascii=False, indent=2)}"
    send_notify_markdown(notify_content)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
