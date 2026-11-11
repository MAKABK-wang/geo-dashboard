#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Review the local suggestion inbox and publish accepted items.

    python scripts/suggestions.py list
    python scripts/suggestions.py show SUG-20261111-101500-AB12
    python scripts/suggestions.py accept SUG-... --title "..." --summary "..." --version 1.1.0
    python scripts/suggestions.py reject SUG-... --reason "缺少可核对的来源"

Accepting only publishes a record. The actual change still has to be made in
data/geo-report.json or templates/index.html, then rebuilt with:

    python scripts/build.py

Contact details stay in the private inbox and are never copied to the public
file (data/accepted-suggestions.json).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUGGEST_DIR = Path(os.environ.get("GEO_SUGGEST_DIR") or (ROOT.parent / ".geo-suggestions"))
INBOX = SUGGEST_DIR / "inbox.jsonl"
PUBLIC_FILE = ROOT / "data" / "accepted-suggestions.json"
DATA_FILE = ROOT / "data" / "geo-report.json"


def read_inbox() -> list[dict]:
    if not INBOX.exists():
        return []
    records = []
    for number, line in enumerate(INBOX.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"warning: skipping malformed line {number}", file=sys.stderr)
    return records


def write_inbox(records: list[dict]) -> None:
    SUGGEST_DIR.mkdir(parents=True, exist_ok=True)
    temp = INBOX.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    temp.replace(INBOX)


def read_public() -> dict:
    if PUBLIC_FILE.exists():
        return json.loads(PUBLIC_FILE.read_text(encoding="utf-8"))
    return {"updated_at": "", "items": []}


def write_public(public: dict) -> None:
    public["updated_at"] = datetime.now().strftime("%Y-%m-%d")
    temp = PUBLIC_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(PUBLIC_FILE)


def site_version() -> str:
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8")).get("version", "1.1.0")
    except (OSError, json.JSONDecodeError):
        return "1.1.0"


def find(records: list[dict], suggestion_id: str) -> dict | None:
    for record in records:
        if record.get("id") == suggestion_id:
            return record
    return None


def excerpt(text: str, length: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= length else text[: length - 1] + "…"


def command_list(args: argparse.Namespace) -> int:
    records = read_inbox()
    if args.status != "all":
        records = [record for record in records if record.get("status", "pending") == args.status]
    if not records:
        print(f"没有状态为 {args.status} 的建议。收件箱：{INBOX}")
        return 0
    records.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    print(f"{'ID':<28} {'状态':<8} {'类型':<6} 创建时间         摘要")
    print("-" * 110)
    for record in records:
        print(
            f"{record.get('id', '-'):<28} {record.get('status', 'pending'):<8} "
            f"{record.get('type', '-'):<6} {record.get('created_at', '')[:19]:<19} "
            f"{excerpt(record.get('message', ''), 44)}"
        )
    print(f"\n共 {len(records)} 条。收件箱：{INBOX}")
    return 0


def command_show(args: argparse.Namespace) -> int:
    record = find(read_inbox(), args.id)
    if not record:
        print(f"找不到建议：{args.id}", file=sys.stderr)
        return 1
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


def command_accept(args: argparse.Namespace) -> int:
    records = read_inbox()
    record = find(records, args.id)
    if not record:
        print(f"找不到建议：{args.id}", file=sys.stderr)
        return 1
    if record.get("status") == "accepted":
        print(f"该建议已采纳：{args.id}")
        return 0

    version = args.version or site_version()
    title = args.title or excerpt(record.get("message", ""), 40)
    summary = args.summary or excerpt(record.get("message", ""), 300)
    public = read_public()
    items = public.setdefault("items", [])
    if any(item.get("id") == args.id for item in items):
        print("公开记录中已存在该 ID，未重复写入。")
    else:
        items.insert(
            0,
            {
                "id": args.id,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "type": record.get("type", "其他"),
                "title": title,
                "summary": summary,
                "submitted_by": args.by,
                "version": version,
            },
        )
        public["items"] = items
        write_public(public)

    record["status"] = "accepted"
    record["reviewed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    record["public_title"] = title
    record["version"] = version
    write_inbox(records)

    print(f"已采纳 {args.id}，写入 {PUBLIC_FILE}")
    print("下一步：修改数据或模板 → python scripts/build.py → 部署。")
    return 0


def command_reject(args: argparse.Namespace) -> int:
    records = read_inbox()
    record = find(records, args.id)
    if not record:
        print(f"找不到建议：{args.id}", file=sys.stderr)
        return 1
    record["status"] = "rejected"
    record["reviewed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    record["reason"] = args.reason or "未说明原因"
    write_inbox(records)
    print(f"已拒绝 {args.id}（理由留在私有收件箱，不公开）。")
    return 0


def command_stats(args: argparse.Namespace) -> int:
    records = read_inbox()
    counts = Counter(record.get("status", "pending") for record in records)
    print(f"收件箱：{INBOX}")
    print(f"总计 {len(records)} 条；待审核 {counts.get('pending', 0)}；已采纳 {counts.get('accepted', 0)}；已拒绝 {counts.get('rejected', 0)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review GEO dashboard suggestions.")
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("list", help="列出建议")
    listing.add_argument("--status", choices=["pending", "accepted", "rejected", "all"], default="pending")
    listing.set_defaults(func=command_list)

    show = sub.add_parser("show", help="查看一条建议的完整内容")
    show.add_argument("id")
    show.set_defaults(func=command_show)

    accept = sub.add_parser("accept", help="采纳并写入公开记录")
    accept.add_argument("id")
    accept.add_argument("--title", default="", help="公开标题（默认取建议摘要）")
    accept.add_argument("--summary", default="", help="公开摘要（默认取建议正文）")
    accept.add_argument("--version", default="", help="版本号（默认读取 data/geo-report.json）")
    accept.add_argument("--by", default="访客", help="公开来源说明")
    accept.set_defaults(func=command_accept)

    reject = sub.add_parser("reject", help="拒绝建议（理由不公开）")
    reject.add_argument("id")
    reject.add_argument("--reason", default="", help="内部理由")
    reject.set_defaults(func=command_reject)

    stats = sub.add_parser("stats", help="统计")
    stats.set_defaults(func=command_stats)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
