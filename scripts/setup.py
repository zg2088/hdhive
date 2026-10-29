#!/usr/bin/env python3
"""Private, offline configuration wizard; application imports are forbidden here."""


import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from urllib.parse import urlsplit


def validate_field(key, value):
    """Reject malformed input without including its value in errors."""
    valid = isinstance(value, str) and value == value.strip() and not any(
        ord(char) < 32 or ord(char) == 127 for char in value)
    if valid and key in {"ADMIN_ID", "TG_API_ID", "API_PORT"}:
        valid = (key == "TG_API_ID" and value == "") or (
            bool(re.fullmatch(r"[1-9][0-9]{0,18}", value))
            and (key != "API_PORT" or int(value) <= 65535))
    elif valid and key == "BOT_TOKEN":
        valid = bool(re.fullmatch(r"[1-9][0-9]{4,15}:[A-Za-z0-9_-]{35}", value))
    elif valid and key == "TG_API_HASH":
        valid = value == "" or bool(re.fullmatch(r"[A-Fa-f0-9]{32}", value))
    elif valid and key == "TG_PHONE":
        valid = value == "" or bool(re.fullmatch(r"\+[1-9][0-9]{6,14}", value))
    elif valid and key == "WEB_USERNAME":
        valid = bool(re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", value))
    elif valid and key in {"WEB_PASSWORD", "WEB_PASSWORD_CONFIRM"}:
        valid = 16 <= len(value) <= 1024
    elif valid and key in {"HDHIVE_CLIENT_ID", "HDHIVE_CLIENT_SECRET"}:
        valid = bool(value) and len(value) <= 4096
    elif valid and key == "HDHIVE_API_KEY":
        valid = len(value) <= 4096
    elif valid and key == "PANEL_ORIGIN":
        try:
            parsed = urlsplit(value)
            host = parsed.hostname or ""
            port = parsed.port
            valid = (parsed.scheme == "https" and bool(host) and not parsed.username
                     and not parsed.password and not parsed.path and not parsed.query
                     and not parsed.fragment and "?" not in value and "#" not in value
                     and "\\" not in value and (port is None or 1 <= port <= 65535))
            if ":" in host:
                ipaddress.IPv6Address(host)
                valid = valid and "%" not in host
            else:
                valid = valid and len(host) <= 253 and all(
                    re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                    for label in host.split("."))
            # Keep the exact origin; forbid syntaxes that .env/Caddy would expand.
            valid = valid and bool(re.fullmatch(r"https://[A-Za-z0-9.\[\]:-]+", value))
        except ValueError:
            valid = False
    if not valid:
        raise ValueError(key + " 格式无效（未显示输入值）")
    return value


def collect_settings(reader):
    """reader(key, prompt, secret) is injectable for offline tests."""
    def ask(key, prompt, secret=True, default=""):
        value = reader(key, prompt, secret)
        return validate_field(key, value if value else default)

    config = {
        "ADMIN_ID": int(ask("ADMIN_ID", "Telegram 管理员数字 ID: ")),
        "BOT_TOKEN": ask("BOT_TOKEN", "BotFather BOT_TOKEN (不回显): "),
        "TG_API_ID": ask("TG_API_ID", "TG_API_ID（可留空）: "),
        "TG_API_HASH": ask("TG_API_HASH", "TG_API_HASH（可留空）: "),
        "TG_PHONE": ask("TG_PHONE", "TG_PHONE（可留空，+国家码）: "),
        "WEB_USERNAME": ask("WEB_USERNAME", "Web 用户名 [admin]: ", False, "admin"),
        "WEB_PASSWORD": ask("WEB_PASSWORD", "Web 密码（至少16字符，不回显）: "),
        "HDHIVE_CLIENT_ID": ask("HDHIVE_CLIENT_ID", "HDHive OAuth Client ID: "),
        "HDHIVE_CLIENT_SECRET": ask("HDHIVE_CLIENT_SECRET", "HDHive OAuth Client Secret: "),
        "HDHIVE_API_KEY": ask("HDHIVE_API_KEY", "HDHIVE_API_KEY（可留空，使用 Client Secret 兜底）: "),
        "TG_SESSION_NAME": "hdhive_user",
        "HDHIVE_API_BASE": "https://hdhive.com/api/open",
        "HDHIVE_AUTH_MODE": "oauth",
        "HDHIVE_WEBHOOK_SECRET": "",
        "UNLOCK_SAFE_MODE": True,
        "PREMIUM_FREE_NEED_APPROVAL": True,
        "AUTO_CHECKIN": False,
        "AI_ENABLE": False,
        "forward_rules": [],
    }
    if bool(config["TG_API_ID"]) != bool(config["TG_API_HASH"]):
        raise ValueError("TG_API_ID 与 TG_API_HASH 必须同时设置或同时留空")
    if ask("WEB_PASSWORD_CONFIRM", "再次输入 Web 密码: ") != config["WEB_PASSWORD"]:
        raise ValueError("Web 两次密码不一致（未显示输入值）")
    deployment = {
        "PANEL_ORIGIN": ask("PANEL_ORIGIN", "面板 HTTPS 源（无路径）[https://localhost:8443]: ", False, "https://localhost:8443"),
        "API_PORT": ask("API_PORT", "本机 API 端口 [8787]: ", False, "8787"),
        "TZ": "Asia/Shanghai",
    }
    config["HDHIVE_REDIRECT_URI"] = deployment["PANEL_ORIGIN"] + "/callback"
    return config, deployment


def ensure_directory(path):
    """Create missing components privately; never follow a symlink component."""
    path = Path(path).absolute()
    for component in (*reversed(path.parents), path):
        try:
            component.mkdir(mode=0o700)
        except FileExistsError:
            if not stat.S_ISDIR(component.lstat().st_mode):
                raise OSError("目录类型不安全，拒绝继续") from None
    return path


def preflight(root, replace):
    """Only metadata is inspected: existing credential contents are never read."""
    for directory in (root / "app", root / "app/data"):
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise OSError("运行目录类型不安全")
    for target in (root / ".env", root / "app/data/config.json"):
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise OSError("配置目标类型不安全")
        if target.exists() and not replace:
            raise FileExistsError("配置已存在；默认不会读取或覆盖")
    data = root / "app/data"
    if data.exists() and not replace and any(data.iterdir()):
        raise FileExistsError("运行数据目录非空；拒绝初始化已有安装")


def generate(directory, reader, *, replace=False):
    """Write JSON secrets and nonsecret Compose settings; never invoke a shell."""
    if os.name != "posix":
        raise OSError("请在 Linux/macOS/WSL POSIX 文件系统中运行以保证权限")
    root = ensure_directory(directory)
    preflight(root, replace)
    lock = root / ".setup.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        preflight(root, replace)
        config, deployment = collect_settings(reader)
        ensure_directory(root / "app/data")
        os.chmod(root / "app/data", 0o700)
        with tempfile.TemporaryDirectory(prefix=".setup-stage-", dir=root) as stage:
            payloads = {
                "config.json": json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                ".env": "# Nonsecret deployment settings; secrets are in app/data/config.json.\n" +
                        "".join(key + "=" + value + "\n" for key, value in deployment.items()),
            }
            for name, text in payloads.items():
                staged = Path(stage) / name
                out = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(out, "w", encoding="utf-8") as handle:
                    os.fchmod(handle.fileno(), 0o600)
                    handle.write(text)
                    handle.flush()
                    os.fsync(handle.fileno())
            preflight(root, replace)
            for name in payloads:
                target = root / ("app/data/config.json" if name == "config.json" else ".env")
                if replace:
                    os.replace(Path(stage) / name, target)
                else:
                    # An exclusive hard-link refuses a target created after preflight.
                    os.link(Path(stage) / name, target, follow_symlinks=False)
        return root / ".env", root / "app/data/config.json"
    finally:
        os.close(fd)
        lock.unlink()


def main(argv=None):
    import argparse
    import getpass
    import sys
    import warnings

    parser = argparse.ArgumentParser(description="HDHive 私密交互初始化（完全离线，不启动服务）")
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parents[1],
                        help="项目根目录（不是凭据参数）")
    parser.add_argument("--replace-config", action="store_true",
                        help="仅替换 .env 与 config.json；不合并旧配置，不自动备份")
    parser.add_argument("--acknowledge-stopped", action="store_true",
                        help="确认服务已停止且自行完成加密备份；配合 --replace-config")
    args = parser.parse_args(argv)
    if args.replace_config and not args.acknowledge_stopped:
        parser.error("--replace-config 必须同时提供 --acknowledge-stopped")
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        print("必须在交互终端运行；拒绝管道、重定向与回显凭据。", file=sys.stderr)
        return 2

    def terminal_reader(key, prompt, secret):
        if secret:
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                return getpass.getpass(prompt)
        return input(prompt)

    try:
        generate(args.directory, terminal_reader, replace=args.replace_config)
    except ValueError as error:
        # Validation errors contain field names only, never submitted values.
        print(str(error), file=sys.stderr)
        return 2
    except (OSError, EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print("未完成：目标已存在、文件系统不安全、无私密终端或输入已取消。请检查目录；不会展示任何凭据。", file=sys.stderr)
        return 2
    print("已生成 .env 与 app/data/config.json（0600）；没有启动服务。")
    print("Web 登录要求可信 HTTPS 反向代理；localhost 默认值不提供证书，也不保证官方允许该 OAuth 回调。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
