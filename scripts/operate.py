#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Operator CLI —— 全权运营 GitHub 上的 GEO 开放仪表盘。

建议闭环（GitHub Pages 公开站）:
    访客在页面提交建议 → 自动变成仓库 Issue(label: suggestion)
    → 运营者运行本脚本审核 → 采纳后:写入公开记录 + 重建 + 提交 + 推送
    → GitHub Actions 自动重新部署 → 页面「建议与修订」更新 → 关闭 Issue

用法:
    python scripts/operate.py issues                      # 列出待处理建议
    python scripts/operate.py show 3                      # 查看 Issue #3 全文
    python scripts/operate.py accept 3 \
        --title "补充 2D/3D 视觉选型对比" \
        --summary "在 FAQ 中新增对比表,并标注适用场景与来源。" \
        --version 1.1.0
    python scripts/operate.py reject 3 --reason "缺少可核对的来源"
    python scripts/operate.py push "更新说明"              # 构建 + 提交 + 推送

GitHub 凭据读取顺序:
    1. 环境变量 GEO_GITHUB_TOKEN
    2. <仓库同级>/.tools/gh-token.txt(本机存储,永不进仓库)

只依赖 Python 标准库;git 需可用(PATH 或常见安装路径)。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "MAKABK-wang/geo-dashboard"
API = f"https://api.github.com/repos/{REPO}"
PAGES_URL = "https://makabk-wang.github.io/geo-dashboard/"
PUBLIC_FILE = ROOT / "data" / "accepted-suggestions.json"
DATA_FILE = ROOT / "data" / "geo-report.json"
LABEL = "suggestion"

GIT_CANDIDATES = [
    "git",
    r"C:\Program Files\Git\cmd\git.exe",
    r"C:\Program Files\Git\bin\git.exe",
    r"C:\Program Files (x86)\Git\cmd\git.exe",
]


def load_token() -> str:
    token = os.environ.get("GEO_GITHUB_TOKEN", "").strip()
    if not token:
        for path in (ROOT.parent / ".tools" / "gh-token.txt", Path.home() / ".geo-gh-token"):
            if path.exists():
                token = path.read_text(encoding="ascii", errors="ignore").strip()
                break
    if not token:
        raise SystemExit("找不到 GitHub token:设置环境变量 GEO_GITHUB_TOKEN,或放置 gh-token.txt")
    return token


TOKEN = load_token()


def build_ssl_context() -> ssl.SSLContext:
    """GitHub API 的 TLS 上下文。

    部分代理/企业环境(如 Clash 等 MITM 代理)会在握手时返回不完整证书链,
    Python 的默认信任库无法验证,而浏览器能验证成功。按需降级并显式告警,
    避免运营命令因环境证书问题完全不可用。

    可通过环境变量强制控制:
        GEO_TLS_VERIFY=1  始终严格校验(失败即报错)
        GEO_TLS_VERIFY=0  跳过校验(仅限可信网络)
    """
    mode = os.environ.get("GEO_TLS_VERIFY", "").strip()
    if mode == "0":
        print("⚠️  GEO_TLS_VERIFY=0:已跳过 TLS 证书校验。", file=sys.stderr)
        return ssl._create_unverified_context()  # noqa: SLF001
    context = ssl.create_default_context()
    if mode == "1":
        return context
    try:
        # 用一次轻量握手探测默认信任库在该网络环境下是否可用
        with urllib.request.urlopen("https://api.github.com", timeout=20, context=context):
            pass
        return context
    except urllib.error.URLError as error:
        if isinstance(error.reason, ssl.SSLError):
            print(
                "⚠️  本机证书链校验失败(通常由本地代理/企业根证书导致),已自动降级为不校验。"
                "如需严格校验请设置 GEO_TLS_VERIFY=1。",
                file=sys.stderr,
            )
            return ssl._create_unverified_context()  # noqa: SLF001
        return context


def api(method: str, path: str, body: dict | None = None) -> dict:
    url = API + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"token {TOKEN}")
    request.add_header("User-Agent", "geo-dashboard-operator")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    if body is not None:
        request.add_header("Content-Type", "application/json")
    context = build_ssl_context()
    try:
        with urllib.request.urlopen(request, timeout=60, context=context) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "ignore")
        raise SystemExit(f"API {method} {path} -> {error.code}: {detail[:300]}")


def find_git() -> str:
    for candidate in GIT_CANDIDATES:
        resolved = shutil.which(candidate) if candidate == "git" else candidate
        if resolved and Path(resolved).exists():
            return resolved
    raise SystemExit("找不到 git:请安装 Git for Windows 或把 git 加入 PATH")


GIT = find_git()


def run(command: list[str]) -> str:
    result = subprocess.run(
        [GIT] + command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise SystemExit(f"git {' '.join(command)} 失败:\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def git(*args: str) -> str:
    return run(list(args))


def site_version() -> str:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return data.get("version", "1.0.0")


def bump_version(current: str) -> str:
    parts = current.split(".")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
    except (ValueError, IndexError):
        return current
    return ".".join(parts)


def read_public() -> dict:
    if PUBLIC_FILE.exists():
        return json.loads(PUBLIC_FILE.read_text(encoding="utf-8"))
    return {"updated_at": "", "items": []}


def write_public(public: dict) -> None:
    public["updated_at"] = datetime.now().strftime("%Y-%m-%d")
    temp = PUBLIC_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(PUBLIC_FILE)


def print_issue(issue: dict) -> None:
    print(f"#{issue['number']:<4} [{issue['state']:<6}] {issue['title']}")
    print(f"      提交者: {issue['user']['login']} · 更新: {issue['updated_at'][:10]} · {issue['html_url']}")


def command_issues(_args: argparse.Namespace) -> int:
    issues = api("GET", f"/issues?state=open&labels={LABEL}&per_page=100")
    if not issues:
        print(f"没有待处理的 {LABEL} Issue。")
        return 0
    print(f"共 {len(issues)} 条待处理建议:\n")
    for issue in issues:
        print_issue(issue)
        print()
    return 0


def command_show(args: argparse.Namespace) -> int:
    issue = api("GET", f"/issues/{args.number}")
    print(f"#{issue['number']} {issue['title']}")
    print(f"状态: {issue['state']} · 提交者: {issue['user']['login']} · {issue['html_url']}")
    print("-" * 72)
    print(issue.get("body") or "(无正文)")
    return 0


def check_clean() -> None:
    status = subprocess.run(
        [GIT, "status", "--porcelain"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.strip()
    if status:
        raise SystemExit("工作区有未提交改动,请先处理:\n" + status)


def build_and_push(message: str) -> None:
    python = sys.executable
    result = subprocess.run(
        [python, str(ROOT / "scripts" / "build.py")],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise SystemExit(f"build.py 失败:\n{result.stdout}\n{result.stderr}")
    git("add", "-A")
    git("commit", "-m", message, "--quiet")
    git("push", "origin", "main")
    print("已构建、提交并推送到 main。GitHub Actions 将自动重新部署。")


def command_accept(args: argparse.Namespace) -> int:
    issue = api("GET", f"/issues/{args.number}")
    if issue.get("pull_request"):
        raise SystemExit(f"#{args.number} 是 Pull Request,不是建议 Issue。")
    if issue["state"] != "open":
        raise SystemExit(f"#{args.number} 已关闭,无需重复处理。")

    check_clean()

    version = args.version or bump_version(site_version())
    title = args.title or issue["title"]
    summary = args.summary or ((issue.get("body") or "").strip()[:300] or issue["title"])

    public = read_public()
    items = public.setdefault("items", [])
    record_id = f"GH-{args.number}"
    if not any(item.get("id") == record_id for item in items):
        items.insert(
            0,
            {
                "id": record_id,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "type": args.type or "访客建议",
                "title": title,
                "summary": summary,
                "submitted_by": issue["user"]["login"],
                "version": version,
            },
        )
        public["items"] = items
        write_public(public)

    commit_message = f"采纳建议 #{args.number}:{title}(v{version})"
    build_and_push(commit_message)

    api(
        "POST",
        f"/issues/{args.number}/comments",
        {"body": f"✅ 已采纳并上线(v{version})。页面「建议与修订」已记录本条修改:https://makabk-wang.github.io/geo-dashboard/#feedback\n\n感谢建议!"},
    )
    api("PATCH", f"/issues/{args.number}", {"state": "closed"})
    print(f"已关闭 Issue #{args.number},公开记录: {PAGES_URL}#feedback")
    return 0


def command_reject(args: argparse.Namespace) -> int:
    issue = api("GET", f"/issues/{args.number}")
    reason = args.reason or "当前无法采纳,感谢反馈。"
    api(
        "POST",
        f"/issues/{args.number}/comments",
        {"body": f"经核对,本建议暂不采纳:{reason}\n\n若补充可核对的来源或信息,可重新提交。"},
    )
    api("PATCH", f"/issues/{args.number}", {"state": "closed"})
    print(f"已关闭 Issue #{args.number}(不采纳)。")
    return 0


def command_push(args: argparse.Namespace) -> int:
    check_clean()
    build_and_push(args.message)
    print(f"部署地址: {PAGES_URL}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="全权运营 GEO 开放仪表盘(仓库 %s)" % REPO)
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("issues", help="列出待处理建议 Issue")
    listing.set_defaults(func=command_issues)

    show = sub.add_parser("show", help="查看 Issue 全文")
    show.add_argument("number", type=int)
    show.set_defaults(func=command_show)

    accept = sub.add_parser("accept", help="采纳建议:重建 + 推送 + 关闭 Issue")
    accept.add_argument("number", type=int)
    accept.add_argument("--title", default="", help="公开标题(默认取 Issue 标题)")
    accept.add_argument("--summary", default="", help="公开摘要(默认取 Issue 正文前 300 字)")
    accept.add_argument("--version", default="", help="版本号(默认自动 +1)")
    accept.add_argument("--type", default="", help="公开类型(默认:访客建议)")
    accept.set_defaults(func=command_accept)

    reject = sub.add_parser("reject", help="不采纳:说明理由并关闭 Issue")
    reject.add_argument("number", type=int)
    reject.add_argument("--reason", default="", help="不采纳理由(公开)")
    reject.set_defaults(func=command_reject)

    push = sub.add_parser("push", help="构建 + 提交 + 推送(内容更新用)")
    push.add_argument("message", help="提交说明")
    push.set_defaults(func=command_push)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
