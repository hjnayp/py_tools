from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path


PROD_OSS_HOST = "oss://meowgames-resource-prod/cattie/"
TEST_OSS_HOST = "oss://meowgames-resource-test/cattie/"


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="上传指定目录或文件到 OSS（通过 ossutil）。",
	)
	parser.add_argument(
		"source",
		help="本地目录或文件路径",
	)
	parser.add_argument(
		"target",
		nargs="?",
		help="完整 OSS 目标路径（例如 oss://bucket/path/）。不传则由 --stage + --channel + --remote-subdir 组合生成",
	)
	parser.add_argument(
		"--stage",
		choices=["1", "2"],
		default="1",
		help="发布环境：2=正式，1=测试（默认）",
	)
	parser.add_argument(
		"--channel",
		default="",
		help="渠道目录名（例如 huawei）；用于自动拼接 OSS 路径",
	)
	parser.add_argument(
		"--remote-subdir",
		default="hot_update/",
		help="远端子目录（默认 hot_update/）",
	)
	parser.add_argument(
		"--ossutil",
		default="",
		help="ossutil 可执行文件路径；不传则自动按仓库结构定位，找不到时回退到 PATH 中的 ossutil",
	)
	parser.add_argument(
		"--config",
		default="",
		help="ossutil 配置文件路径；不传则自动按仓库结构定位",
	)
	parser.add_argument(
		"--update",
		action="store_true",
		help="仅上传较新文件（等价 ossutil -u）",
	)
	parser.add_argument(
		"--force",
		action="store_true",
		help="覆盖远端同名文件（等价 ossutil -f）",
	)
	parser.add_argument(
		"--dry-run",
		action="store_true",
		help="只打印命令，不执行",
	)
	return parser.parse_args()


def repo_root() -> Path:
	return Path(__file__).resolve().parents[2]


def default_ossutil_path() -> str:
	candidate = repo_root() / "jekins_tools" / "publish" / "ossutil" / "ossutil.exe"
	return str(candidate) if candidate.exists() else "ossutil"


def default_config_path() -> str:
	candidate = repo_root() / "jekins_tools" / "publish" / "ossutil" / "meowgames.ossutilconfig"
	return str(candidate)


def choose_oss_host(stage: str) -> str:
	return PROD_OSS_HOST if stage == "2" else TEST_OSS_HOST


def normalize_remote_path(path: str) -> str:
	normalized = path.replace("\\", "/")
	if not normalized.startswith("oss://"):
		raise ValueError(f"OSS 目标路径必须以 oss:// 开头，当前为: {path}")
	return normalized


def build_target(args: argparse.Namespace) -> str:
	if args.target:
		return normalize_remote_path(args.target)

	host = choose_oss_host(args.stage)
	channel = args.channel.strip("/")
	remote_subdir = args.remote_subdir.strip("/")

	parts = [host.rstrip("/")]
	if channel:
		parts.append(channel)
	if remote_subdir:
		parts.append(remote_subdir)

	return normalize_remote_path("/".join(parts) + "/")


def build_command(
	source: Path,
	target: str,
	ossutil: str,
	config: str,
	force: bool,
	update: bool,
) -> list[str]:
	action = "sync" if source.is_dir() else "cp"

	cmd = [ossutil, action, str(source), target]
	if config:
		cmd.extend(["-c", config])
	if force:
		cmd.append("-f")
	if update:
		cmd.append("-u")
	return cmd


def main() -> int:
	args = parse_args()

	source = Path(args.source).expanduser().resolve()
	if not source.exists():
		print(f"[ERROR] 本地路径不存在: {source}")
		return 1

	target = build_target(args)
	ossutil = args.ossutil or default_ossutil_path()
	config = args.config or default_config_path()

	if config and not Path(config).exists():
		print(f"[WARN] 未找到 ossutil 配置文件: {config}")
		print("       将尝试使用 ossutil 默认配置（如环境变量或用户级配置）")
		config = ""

	command = build_command(
		source=source,
		target=target,
		ossutil=ossutil,
		config=config,
		force=args.force,
		update=args.update,
	)

	print("[INFO] 上传类型:", "目录 sync" if source.is_dir() else "文件 cp")
	print("[INFO] 本地路径:", source)
	print("[INFO] OSS 目标:", target)
	print("[INFO] 执行命令:", " ".join(shlex.quote(part) for part in command))

	if args.dry_run:
		print("[INFO] dry-run 模式，未执行上传")
		return 0

	try:
		result = subprocess.run(command, check=False)
		if result.returncode != 0:
			print(f"[ERROR] 上传失败，退出码: {result.returncode}")
			return result.returncode
	except FileNotFoundError:
		print(f"[ERROR] 找不到 ossutil 可执行文件: {ossutil}")
		print("       请通过 --ossutil 指定绝对路径，或将 ossutil 加入 PATH")
		return 1
	except OSError as exc:
		print(f"[ERROR] 执行失败: {exc}")
		return 1

	print("[INFO] 上传完成")
	return 0


if __name__ == "__main__":
	sys.exit(main())
