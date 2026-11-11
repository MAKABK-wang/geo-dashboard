#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local preview server with a small, dependency-free suggestion API.

    python scripts/serve.py
    python scripts/serve.py --port 8123 --host 0.0.0.0

The API is intentionally minimal: it appends validated suggestions to a JSONL
inbox outside the web root, so personal contact details are never served as
static files. Review them with scripts/suggestions.py.

When the site is hosted on a purely static platform (GitHub Pages, Netlify,
Cloudflare Pages), this endpoint does not exist; the browser then falls back
to a prefilled GitHub Issue.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SUGGEST_DIR = Path(os.environ.get("GEO_SUGGEST_DIR") or (ROOT.parent / ".geo-suggestions"))
INBOX = SUGGEST_DIR / "inbox.jsonl"
SALT_FILE = SUGGEST_DIR / ".salt"

ALLOWED_TYPES = {"数据修正", "内容补充", "体验问题", "其他"}
MAX_BODY = 32 * 1024
RATE_LIMIT = 5
RATE_WINDOW = 600
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

_rate_lock = threading.Lock()
_rates: dict[str, deque[float]] = defaultdict(deque)
_write_lock = threading.Lock()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def get_salt() -> bytes:
    SUGGEST_DIR.mkdir(parents=True, exist_ok=True)
    if SALT_FILE.exists():
        return SALT_FILE.read_bytes()
    salt = secrets.token_bytes(32)
    SALT_FILE.write_bytes(salt)
    try:
        SALT_FILE.chmod(0o600)
    except OSError:
        pass
    return salt


def hash_ip(ip: str) -> str:
    return hashlib.sha256(get_salt() + ip.encode("utf-8", "ignore")).hexdigest()[:16]


def clean(value, limit: int) -> str:
    text = CONTROL_CHARS.sub("", str(value or "")).strip()
    return text[:limit]


def rate_limited(ip: str) -> bool:
    now = time.monotonic()
    with _rate_lock:
        bucket = _rates[ip]
        while bucket and now - bucket[0] > RATE_WINDOW:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT:
            return True
        bucket.append(now)
        return False


def append_inbox(record: dict) -> None:
    SUGGEST_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _write_lock:
        with INBOX.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())


class SuggestionHandler(SimpleHTTPRequestHandler):
    server_version = "GeoOpenDashboard/1.0"
    # Windows can map .js to text/plain; with nosniff that blocks the script.
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript; charset=utf-8",
        ".mjs": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".svg": "image/svg+xml",
        ".webmanifest": "application/manifest+json",
        ".txt": "text/plain; charset=utf-8",
        ".xml": "application/xml; charset=utf-8",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def json_response(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            self.json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "geo-suggestions",
                    "inbox": str(INBOX),
                    "time": now_iso(),
                },
            )
            return
        if path == "/api/suggestions":
            self.json_response(
                HTTPStatus.METHOD_NOT_ALLOWED,
                {"ok": False, "error": "审核队列仅限维护者在本地读取。"},
            )
            return
        super().do_GET()

    def do_PUT(self):
        self.json_response(
            HTTPStatus.METHOD_NOT_ALLOWED,
            {"ok": False, "error": "本服务器为只读发布层，不接受 PUT。"},
        )

    def do_DELETE(self):
        self.json_response(
            HTTPStatus.METHOD_NOT_ALLOWED,
            {"ok": False, "error": "本服务器为只读发布层，不接受 DELETE。"},
        )

    def do_PATCH(self):
        self.json_response(
            HTTPStatus.METHOD_NOT_ALLOWED,
            {"ok": False, "error": "本服务器为只读发布层，不接受 PATCH。"},
        )

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/suggestions":
            self.json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            self.json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "缺少请求内容。"})
            return
        if length > MAX_BODY:
            self.json_response(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"ok": False, "error": "建议内容过长。"})
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "请求格式不是有效 JSON。"})
            return
        if not isinstance(payload, dict):
            self.json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "请求格式不正确。"})
            return

        ip = self.client_address[0]
        if payload.get("website"):
            # Honeypot: pretend success, never store.
            self.json_response(
                HTTPStatus.OK,
                {"ok": True, "id": "SUG-" + secrets.token_hex(4).upper(), "received_at": now_iso()},
            )
            return

        suggestion_type = clean(payload.get("type"), 20)
        if suggestion_type not in ALLOWED_TYPES:
            self.json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "请选择有效的建议类型。"})
            return

        message = clean(payload.get("message"), 1001)
        if len(message) < 10:
            self.json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "建议内容至少需要 10 个字。"})
            return
        if len(message) > 1000:
            self.json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "建议内容请控制在 1000 字以内。"})
            return

        if rate_limited(ip):
            self.json_response(HTTPStatus.TOO_MANY_REQUESTS, {"ok": False, "error": "提交过于频繁，请稍后再试。"})
            return

        record = {
            "id": "SUG-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2).upper(),
            "created_at": now_iso(),
            "status": "pending",
            "type": suggestion_type,
            "location": clean(payload.get("location"), 120),
            "message": message,
            "contact": clean(payload.get("contact"), 120),
            "page": clean(payload.get("page"), 300),
            "ip_hash": hash_ip(ip),
            "ua": clean(self.headers.get("User-Agent"), 200),
        }
        append_inbox(record)
        print(f"[suggestion] {record['id']} {suggestion_type} -> {INBOX}")
        self.json_response(
            HTTPStatus.CREATED,
            {"ok": True, "id": record["id"], "received_at": record["created_at"]},
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview the GEO dashboard and collect suggestions.")
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    SUGGEST_DIR.mkdir(parents=True, exist_ok=True)
    get_salt()
    server = ThreadingHTTPServer((args.host, args.port), SuggestionHandler)
    display_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
    print("GEO dashboard preview")
    print(f"  page      http://{display_host}:{args.port}/")
    print(f"  API       POST http://{display_host}:{args.port}/api/suggestions")
    print(f"  inbox     {INBOX}")
    print("  review    python scripts/suggestions.py list")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
