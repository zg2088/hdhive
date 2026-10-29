#!/usr/bin/env python3
"""Strict release-file allowlist. Does not inspect credentials or Git history."""
from pathlib import Path
import os
import sys

PUBLIC_FILES = frozenset({
    "README.md", ".gitignore", ".env.example", "config.example.json", "compose.yaml",
    "docs/HTTPS.md", "docs/VERIFICATION.md", "scripts/setup.py", "scripts/verify_public.py",
    "tests/test_setup.py", "tests/test_cli.py", "tests/test_distribution.py", "tests/test_export.py",
})
PUBLIC_DIRECTORIES = frozenset({"docs", "scripts", "tests"})


def audit(directory):
    """Return only relative paths violating the explicit public-file boundary."""
    root = Path(directory)
    problems = set()
    seen = set()
    for current, directories, files in os.walk(root, followlinks=False):
        for name in list(directories):
            path = Path(current) / name
            relative = path.relative_to(root).as_posix()
            if relative == ".git" and not path.is_symlink():
                directories.remove(name)
                continue
            if path.is_symlink() or relative not in PUBLIC_DIRECTORIES:
                problems.add(relative)
                directories.remove(name)
        for name in files:
            path = Path(current) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink() or not path.is_file() or relative not in PUBLIC_FILES:
                problems.add(relative)
            else:
                seen.add(relative)
    problems.update(PUBLIC_FILES - seen)
    return sorted(problems)


def main():
    problems = audit(Path(__file__).resolve().parents[1])
    if problems:
        print("公开文件边界检查失败；意外、缺失或不安全的相对路径：", file=sys.stderr)
        for path in problems:
            print(path, file=sys.stderr)
        return 1
    print("公开文件边界检查通过：仅安装器、示例配置、文档及离线测试。未检查 Git 历史或文件内容。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
