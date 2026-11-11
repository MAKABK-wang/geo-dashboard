#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the static, searchable GEO dashboard from data/geo-report.json.

The site is intentionally dependency-free (Python standard library only).
Run from anywhere:

    python scripts/build.py
    python scripts/build.py --base-url https://example.com/geo-dashboard/
    python scripts/build.py --check     # fail if generated files are stale

Outputs:
    index.html
    index.md
    llms.txt
    robots.txt
    sitemap.xml              (only when a base URL is configured)
    data/faq-schema.json
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "geo-report.json"
TEMPLATE_FILE = ROOT / "templates" / "index.html"

NAV_ITEMS = [
    ("overview", "概览"),
    ("gap", "检测"),
    ("brands", "品牌"),
    ("audit", "审计"),
    ("assets", "资产"),
    ("roadmap", "路线"),
    ("channels", "渠道"),
    ("faq", "FAQ"),
    ("method", "数据"),
]
FEEDBACK_NAV = ("feedback", "建议")

ASSET_ICONS = {
    "book": "i-book",
    "target": "i-target",
    "doc": "i-doc",
    "chat": "i-chat",
    "braces": "i-braces",
    "chart": "i-chart",
    "code": "i-code",
}

AUDIT_ICONS = {"pass": "i-check", "fail": "i-close"}


def esc(value) -> str:
    return html.escape(str(value), quote=False)


def attr(value) -> str:
    return html.escape(str(value), quote=True)


def icon(name: str, cls: str = "") -> str:
    classes = "icon" + (f" {cls}" if cls else "")
    return f'<svg class="{classes}" aria-hidden="true"><use href="#{name}"/></svg>'


# --------------------------------------------------------------------------- markdown
def md_inline(text: str) -> str:
    """Small, safe inline Markdown renderer: bold + http(s) links."""
    text = html.escape(text, quote=True)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        lambda m: f'<a href="{m.group(2)}" target="_blank" rel="noopener noreferrer">{m.group(1)}</a>',
        text,
    )
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return text


def md_to_html(text: str) -> str:
    blocks: list[str] = []
    paragraph: list[str] = []
    items: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append("<p>" + md_inline(" ".join(paragraph)) + "</p>")
            paragraph.clear()

    def flush_list() -> None:
        if items:
            blocks.append("<ul>" + "".join(f"<li>{md_inline(item)}</li>" for item in items) + "</ul>")
            items.clear()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            flush_list()
            continue
        if line.startswith("- "):
            flush_paragraph()
            items.append(line[2:])
        else:
            flush_list()
            paragraph.append(line)
    flush_paragraph()
    flush_list()
    return "\n".join(blocks)


# --------------------------------------------------------------------------- metrics
def compute(data: dict) -> dict:
    queries = data["queries"]
    total = len(queries)
    mentioned = sum(1 for query in queries if query.get("brand_mentioned"))
    cited = sum(1 for query in queries if query.get("domain_cited"))
    brands_total = sum(len(query["brands"]) for query in queries)
    checks = data["audit"]["checks"]
    audit_pass = sum(1 for check in checks if check["status"] == "pass")
    faq_count = len(data["faq"]["items"])

    doc_like = sum(
        1 for asset in data["assets"]
        if asset["tag"] in {"方法论", "策略", "分析"}
        or (asset["tag"] == "内容" and "FAQ" not in asset["title"])
    )
    schema_like = sum(1 for asset in data["assets"] if asset["tag"] == "技术")
    tools = sum(1 for asset in data["assets"] if asset["tag"] == "工具")

    return {
        "total_queries": total,
        "mentioned": mentioned,
        "cited": cited,
        "mention_rate": (mentioned / total * 100) if total else 0.0,
        "domain_rate": (cited / total * 100) if total else 0.0,
        "brands_total": brands_total,
        "brands_avg": (brands_total / total) if total else 0.0,
        "audit_pass": audit_pass,
        "audit_total": len(checks),
        "audit_rate": (audit_pass / len(checks) * 100) if checks else 0.0,
        "faq_count": faq_count,
        "asset_count": faq_count + doc_like + schema_like + tools,
    }


# --------------------------------------------------------------------------- fragments
def render_nav_links() -> str:
    return "\n".join(
        f'<a href="#{anchor}" data-nav>{esc(label)}</a>' for anchor, label in NAV_ITEMS
    )


def render_mobile_nav() -> str:
    items = NAV_ITEMS + [FEEDBACK_NAV]
    return "\n".join(f'<a href="#{anchor}">{esc(label)}</a>' for anchor, label in items)


def render_footer_nav() -> str:
    items = NAV_ITEMS + [FEEDBACK_NAV]
    return "\n".join(f'<a href="#{anchor}">{esc(label)}</a>' for anchor, label in items)


def load_accepted_suggestions() -> dict:
    path = ROOT / "data" / "accepted-suggestions.json"
    if not path.exists():
        return {"updated_at": "", "items": []}
    return json.loads(path.read_text(encoding="utf-8"))


def render_accepted_items(accepted: dict) -> str:
    items = accepted.get("items", [])
    if not items:
        return '<p class="accepted-empty">还没有公开采纳记录。第一条建议可能来自你。</p>'
    cards = []
    for item in items:
        cards.append(
            f'<article class="accepted-item" id="accepted-{attr(item["id"].lower())}" data-search-item '
            f'data-search-title="{attr("已采纳建议：" + item["title"])}" data-search-type="已采纳建议" '
            f'data-search-section="建议与修订">\n'
            f'  <div class="accepted-top"><span class="badge badge-pass">已采纳</span>'
            f'<span class="accepted-type">{esc(item["type"])}</span>'
            f'<time datetime="{attr(item["date"])}">{esc(item["date"])}</time></div>\n'
            f'  <h4>{esc(item["title"])}</h4>\n'
            f'  <p>{esc(item["summary"])}</p>\n'
            f'  <p class="accepted-meta">来源：{esc(item["submitted_by"])} · v{esc(item["version"])} · {esc(item["id"])}</p>\n'
            f'</article>'
        )
    return "\n".join(cards)


def render_repo_link(data: dict) -> str:
    url = (data["site"].get("repo_url") or "").strip()
    if not url:
        return ""
    return (
        f'<a class="icon-btn" href="{attr(url)}" target="_blank" rel="noopener noreferrer" '
        f'aria-label="查看源代码仓库">{icon("i-github")}</a>'
    )


def kpi_value(kpi: dict, metrics: dict) -> tuple[str, str, str]:
    key = kpi["key"]
    if key == "mention_rate":
        return (
            f'{metrics["mention_rate"]:.0f}<span class="unit">%</span>',
            f'品牌提及率 {metrics["mention_rate"]:.0f}%',
            metrics["mention_rate"],
        )
    if key == "domain_rate":
        return (
            f'{metrics["domain_rate"]:.0f}<span class="unit">%</span>',
            f'域名引用率 {metrics["domain_rate"]:.0f}%',
            metrics["domain_rate"],
        )
    if key == "audit_rate":
        return (
            f'{metrics["audit_pass"]}<span class="unit">/ {metrics["audit_total"]}</span>',
            f'站点可读性 {metrics["audit_pass"]}/{metrics["audit_total"]}',
            metrics["audit_rate"],
        )
    if key == "asset_count":
        return (
            str(metrics["asset_count"]),
            f'内容资产 {metrics["asset_count"]} 项',
            100.0,
        )
    raise ValueError(f"unknown KPI key: {key}")


def render_kpis(data: dict, metrics: dict) -> str:
    cards = []
    for kpi in data["kpis"]:
        value, title, percent = kpi_value(kpi, metrics)
        tone = kpi["tone"]
        width = max(2.0, min(100.0, percent)) if percent else 0.0
        cards.append(
            f'<article class="card kpi" id="kpi-{attr(kpi["key"])}" data-search-item '
            f'data-search-title="{attr(title)}" data-search-type="核心指标" data-search-section="核心指标">\n'
            f'  <div class="kpi-top"><span class="kpi-label">{esc(kpi["label"])}</span>'
            f'<span class="kpi-icon tone-{attr(tone)}">{icon("i-" + kpi["icon"])}</span></div>\n'
            f'  <div class="kpi-value {attr(tone)}">{value}</div>\n'
            f'  <div class="kpi-meter {attr(tone)}"><span style="width:{width:.0f}%"></span></div>\n'
            f'  <p class="kpi-note">{esc(kpi["note"])}</p>\n'
            f'</article>'
        )
    return "\n".join(cards)


def render_gap_rows(data: dict) -> str:
    max_units = max(len(query["brands"]) for query in data["queries"])
    rows = []
    for index, query in enumerate(data["queries"], start=1):
        count = len(query["brands"])
        units = "".join(
            '<span class="unit on" aria-hidden="true"></span>' if slot < count
            else '<span class="unit" aria-hidden="true"></span>'
            for slot in range(max_units)
        )
        rows.append(
            f'<div class="gap-row" id="gap-{attr(query["id"])}" data-search-item '
            f'data-search-title="{attr(query["short"] + "：竞品推荐 " + str(count) + " 家，合一 0 家")}" '
            f'data-search-type="检测问题" data-search-section="AI 搜索检测结果">\n'
            f'  <div class="gap-q"><span class="gap-idx">{index:02d}</span>\n'
            f'    <span class="gap-qtext"><b>{esc(query["short"])}</b><small>{esc(query["question"])}</small></span>\n'
            f'  </div>\n'
            f'  <div class="gap-units" role="img" aria-label="{attr("AI 推荐竞品 " + str(count) + " 家，合一自动化 0 家")}">{units}</div>\n'
            f'  <div class="gap-count"><b>{count}</b><small>家竞品</small></div>\n'
            f'  <div class="gap-brand"><span class="zero" aria-hidden="true">0</span><small>合一</small></div>\n'
            f'</div>'
        )
    return "\n".join(rows)


def render_answers(data: dict) -> str:
    blocks = []
    for index, query in enumerate(data["queries"], start=1):
        blocks.append(
            f'<details class="answer-item" id="answer-{attr(query["id"])}" data-search-item '
            f'data-search-title="{attr("AI 原回答：" + query["question"])}" data-search-type="AI 原回答" '
            f'data-search-section="AI 搜索检测结果">\n'
            f'  <summary><span class="answer-index">Q{index}</span>'
            f'<span class="answer-summary">{esc(query["question"])}</span>'
            f'<span class="answer-badge">未提及合一</span>{icon("i-chevron", "answer-chevron")}</summary>\n'
            f'  <div class="answer-body">{md_to_html(query["answer"])}\n'
            f'    <p class="answer-foot">回答中出现的竞品：{esc("、".join(query["brands"]))} · '
            f'<a href="#brands">返回品牌对照表</a></p>\n'
            f'  </div>\n'
            f'</details>'
        )
    return "\n".join(blocks)


def render_competitor_rows(data: dict) -> str:
    rows = []
    for index, query in enumerate(data["queries"], start=1):
        pills = "".join(f'<span class="pill">{esc(brand)}</span>' for brand in query["brands"])
        status = '<span class="pill pill-danger">未出现</span>' if not query["brand_mentioned"] else '<span class="pill pill-accent">已提及</span>'
        rows.append(
            f'<tr id="brand-{attr(query["id"])}" data-search-item '
            f'data-search-title="{attr(query["question"] + "：AI 推荐 " + "、".join(query["brands"]))}" '
            f'data-search-type="品牌对照" data-search-section="AI 实际推荐了谁">\n'
            f'  <th scope="row" class="row-q"><span class="row-idx">{index:02d}</span>{esc(query["question"])}</th>\n'
            f'  <td><div class="pills">{pills}</div></td>\n'
            f'  <td>{status}</td>\n'
            f'  <td><a class="link-quiet" href="#answer-{attr(query["id"])}">原回答</a></td>\n'
            f'</tr>'
        )
    return "\n".join(rows)


def render_audit_cards(data: dict, metrics: dict) -> str:
    cards = []
    for check in data["audit"]["checks"]:
        passed = check["status"] == "pass"
        status_class = "pass" if passed else "fail"
        badge_class = "badge-pass" if passed else "badge-fail"
        badge_label = "通过" if passed else "未通过"
        cards.append(
            f'<article class="audit-card {status_class}" id="audit-{attr(check["id"])}" data-search-item '
            f'data-search-title="{attr(check["title"] + "：" + badge_label)}" data-search-type="审计项" '
            f'data-search-section="站点机器可读性审计">\n'
            f'  <div class="audit-head"><span class="audit-status">{icon(AUDIT_ICONS[check["status"]])}</span>'
            f'<h3>{esc(check["title"])}</h3><span class="badge {badge_class}">{badge_label}</span></div>\n'
            f'  <p class="audit-detail">{esc(check["detail"])}</p>\n'
            f'  <p class="audit-fix"><span>修复建议</span>{esc(check["fix"])}</p>\n'
            f'</article>'
        )
    return "\n".join(cards)


def render_asset_cards(data: dict) -> str:
    cards = []
    for index, asset in enumerate(data["assets"], start=1):
        href = (asset.get("href") or "").strip()
        icon_name = ASSET_ICONS.get(asset.get("icon", "doc"), "i-doc")
        inner = (
            f'<div class="asset-top"><span class="asset-icon">{icon(icon_name)}</span>'
            f'<span class="asset-tag">{esc(asset["tag"])}</span></div>\n'
            f'<h3>{esc(asset["title"])}</h3>\n'
            f'<p>{esc(asset["desc"])}</p>'
        )
        if href:
            cta = "站内查看" if href.startswith("#") else "下载文件"
            inner += f'\n<span class="asset-cta">{cta}{icon("i-arrow-right")}</span>'
            download = ' download' if not href.startswith("#") else ""
            cards.append(
                f'<a class="asset-card" href="{attr(href)}"{download} id="asset-{index}" data-search-item '
                f'data-search-title="{attr(asset["title"] + "：" + asset["desc"])}" data-search-type="内容资产" '
                f'data-search-section="GEO 内容资产">{inner}</a>'
            )
        else:
            cards.append(
                f'<article class="asset-card" id="asset-{index}" data-search-item '
                f'data-search-title="{attr(asset["title"] + "：" + asset["desc"])}" data-search-type="内容资产" '
                f'data-search-section="GEO 内容资产">{inner}</article>'
            )
    return "\n".join(cards)


def render_roadmap(data: dict) -> str:
    items = []
    for step in data["roadmap"]:
        items.append(
            f'<div class="road-item" id="roadmap-{attr(step["id"].lower())}" data-search-item '
            f'data-search-title="{attr(step["id"] + " " + step["title"] + "：" + step["desc"])}" '
            f'data-search-type="改造步骤" data-search-section="GEO 改造路线图">\n'
            f'  <div class="road-marker" aria-hidden="true">{esc(step["id"])}</div>\n'
            f'  <div class="road-body">\n'
            f'    <div class="road-top"><h3>{esc(step["title"])}</h3><span class="road-phase">{esc(step["phase"])}</span></div>\n'
            f'    <p>{esc(step["desc"])}</p>\n'
            f'    <p class="road-signal"><span>验收信号</span>{esc(step["signal"])}</p>\n'
            f'  </div>\n'
            f'</div>'
        )
    return "\n".join(items)


def render_channel_rows(data: dict) -> str:
    rows = []
    for index, channel in enumerate(data["channels"], start=1):
        pills = "".join(f'<span class="pill">{esc(item)}</span>' for item in channel["channels"])
        rows.append(
            f'<tr id="channel-{index}" data-search-item '
            f'data-search-title="{attr(channel["ai"] + "：" + channel["source"] + " · " + "、".join(channel["channels"]))}" '
            f'data-search-type="渠道" data-search-section="国内 AI 检索地图">\n'
            f'  <td><b>{esc(channel["ai"])}</b><span class="vendor">{esc(channel["vendor"])}</span></td>\n'
            f'  <td>{esc(channel["source"])}</td>\n'
            f'  <td><div class="pills">{pills}</div></td>\n'
            f'  <td><span class="period">{esc(channel["period"])}</span></td>\n'
            f'</tr>'
        )
    return "\n".join(rows)


def render_risk_cards(data: dict) -> str:
    cards = []
    for index, risk in enumerate(data["risks"], start=1):
        badge = "badge-danger" if risk["severity"] == "高" else "badge-warn"
        cards.append(
            f'<article class="risk-card" id="risk-{index}" data-search-item '
            f'data-search-title="{attr(risk["title"] + "：" + risk["desc"])}" data-search-type="风险" '
            f'data-search-section="现状警示">\n'
            f'  <div class="risk-top"><span class="risk-icon">{icon("i-alert")}</span>'
            f'<span class="badge {badge}">风险 {esc(risk["severity"])}</span></div>\n'
            f'  <h3>{esc(risk["title"])}</h3>\n'
            f'  <p>{esc(risk["desc"])}</p>\n'
            f'</article>'
        )
    return "\n".join(cards)


def render_faq(data: dict) -> tuple[str, str]:
    categories = {category["id"]: category for category in data["faq"]["categories"]}
    items_by_category: dict[str, list[dict]] = {key: [] for key in categories}
    for item in data["faq"]["items"]:
        items_by_category[item["category"]].append(item)

    filters = [
        f'<button class="chip" type="button" data-filter="all" data-label="全部" aria-pressed="true">'
        f'全部 <span class="count">{len(data["faq"]["items"])}</span></button>'
    ]
    for category in data["faq"]["categories"]:
        count = len(items_by_category[category["id"]])
        filters.append(
            f'<button class="chip" type="button" data-filter="{attr(category["id"])}" '
            f'data-label="{attr(category["name"])}" aria-pressed="false">'
            f'{esc(category["name"])} <span class="count">{count}</span></button>'
        )

    groups = []
    for category in data["faq"]["categories"]:
        items = items_by_category[category["id"]]
        rendered_items = []
        for item in items:
            number = item["id"].upper()
            answer = esc(item["a"]).replace("\n", "<br>")
            rendered_items.append(
                f'<details class="faq-item" id="faq-{attr(item["id"])}" data-faq-category="{attr(category["id"])}" '
                f'data-search-item data-search-title="{attr(number + " " + item["q"])}" data-search-type="FAQ" '
                f'data-search-section="{attr("FAQ · " + category["name"])}">\n'
                f'  <summary><span class="faq-index">{esc(number)}</span>'
                f'<span class="faq-question">{esc(item["q"])}</span>{icon("i-chevron", "faq-chevron")}</summary>\n'
                f'  <div class="faq-body"><p class="faq-answer">{answer}</p>\n'
                f'    <div class="faq-actions">\n'
                f'      <button class="text-btn" type="button" data-copy-selector="#faq-{attr(item["id"])} .faq-answer">复制答案</button>\n'
                f'      <button class="text-btn" type="button" data-copy-link="faq-{attr(item["id"])}">复制链接</button>\n'
                f'    </div>\n'
                f'  </div>\n'
                f'</details>'
            )
        groups.append(
            f'<div class="faq-group" data-faq-group="{attr(category["id"])}">\n'
            f'  <div class="faq-group-head"><h3>{esc(category["name"])} <span class="count">{len(items)}</span></h3>'
            f'<p>{esc(category["desc"])}</p></div>\n'
            f'  {"".join(rendered_items)}\n'
            f'</div>'
        )
    return "\n".join(filters), "\n".join(groups)


def render_method(data: dict) -> tuple[str, str, str, str]:
    metrics = "".join(
        f'<tr><td>{esc(row["name"])}</td><td>{esc(row["definition"])}</td><td>{esc(row["result"])}</td></tr>'
        for row in data["method"]["metrics"]
    )
    steps = "".join(f"<li>{esc(step)}</li>" for step in data["method"]["steps"])
    limitations = "".join(f"<li>{esc(item)}</li>" for item in data["method"]["limitations"])
    changelog = "".join(
        f'<li><time datetime="{attr(entry["date"])}">{esc(entry["date"])}</time><span>{esc(entry["text"])}</span></li>'
        for entry in data["changelog"]
    )
    return metrics, steps, limitations, changelog


def render_downloads(files: list[tuple[str, str, int]]) -> str:
    cards = []
    for href, label, size in files:
        if label.endswith(".json"):
            icon_name = "i-braces"
        elif label.endswith(".md"):
            icon_name = "i-doc"
        else:
            icon_name = "i-chat"
        cards.append(
            f'<a class="download-card" href="{attr(href)}" download>'
            f'{icon(icon_name)}'
            f'<span class="download-name">{esc(label)}<small>{size} KB</small></span>'
            f'{icon("i-download", "download-arrow")}</a>'
        )
    return "\n".join(cards)


# --------------------------------------------------------------------------- SEO head
def jsonld_graph(data: dict, base_url: str) -> dict:
    site = data["site"]
    brand = data["brand"]
    snapshot = data["snapshot"]
    metrics = compute(data)
    org_id = brand["url"].rstrip("/") + "/#organization"

    organization = {
        "@type": "Organization",
        "@id": org_id,
        "name": brand["legal_name"],
        "alternateName": [brand["name"]] + brand["aliases"][:3],
        "url": brand["url"],
        "description": brand["description"],
        "address": {
            "@type": "PostalAddress",
            "addressRegion": brand["address"]["region"],
            "addressLocality": brand["address"]["locality"],
        },
    }

    faq = {
        "@type": "FAQPage",
        "@id": (base_url + "#faq") if base_url else "#faq",
        "name": "合一自动化 FAQ 知识库",
        "inLanguage": site["lang"],
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
            }
            for item in data["faq"]["items"]
        ],
        "about": {"@id": org_id},
    }

    graph = [organization, faq]

    if base_url:
        webpage_id = base_url + "#webpage"
        dataset_id = base_url + "#dataset"
        graph = [
            {
                "@type": "WebSite",
                "@id": base_url + "#website",
                "url": base_url,
                "name": site["short_name"],
                "inLanguage": site["lang"],
                "publisher": {"@id": org_id},
                "potentialAction": {
                    "@type": "SearchAction",
                    "target": {
                        "@type": "EntryPoint",
                        "urlTemplate": base_url + "?q={search_term_string}",
                    },
                    "query-input": "required name=search_term_string",
                },
            },
            {
                "@type": "WebPage",
                "@id": webpage_id,
                "url": base_url,
                "name": site["title"],
                "description": site["description"],
                "isPartOf": {"@id": base_url + "#website"},
                "inLanguage": site["lang"],
                "datePublished": snapshot["published_at"],
                "dateModified": snapshot["published_at"],
                "license": site["license_data_url"],
                "about": {"@id": org_id},
                "mainEntity": {"@id": dataset_id},
            },
            {
                "@type": "Dataset",
                "@id": dataset_id,
                "name": "合一自动化 AI 搜索可见性快照（2026-10-31）",
                "description": (
                    f"5 个工业视觉核心问题的 AI 搜索检测数据：品牌提及 {metrics['mentioned']}/{metrics['total_queries']}，"
                    f"域名引用 {metrics['cited']}/{metrics['total_queries']}；含 30 条 FAQ、站点审计与检测方法。"
                ),
                "creator": {"@id": org_id},
                "datePublished": snapshot["published_at"],
                "inLanguage": site["lang"],
                "license": site["license_data_url"],
                "keywords": site["keywords"],
                "distribution": [
                    {
                        "@type": "DataDownload",
                        "contentUrl": base_url + "data/geo-report.json",
                        "encodingFormat": "application/json",
                        "name": "完整开放数据（JSON）",
                    },
                    {
                        "@type": "DataDownload",
                        "contentUrl": base_url + "index.md",
                        "encodingFormat": "text/markdown",
                        "name": "Markdown 全文",
                    },
                ],
            },
            organization,
            faq,
        ]

    return {"@context": "https://schema.org", "@graph": graph}


def render_head_extra(data: dict, base_url: str) -> str:
    site = data["site"]
    parts = []
    if base_url:
        parts.append(f'<link rel="canonical" href="{attr(base_url)}">')
        parts.append(f'<meta property="og:url" content="{attr(base_url)}">')
    graph = json.dumps(jsonld_graph(data, base_url), ensure_ascii=False, indent=2)
    graph = graph.replace("</", "<\\/")
    parts.append('<script type="application/ld+json">\n' + graph + "\n</script>")
    return "\n".join(parts)


# --------------------------------------------------------------------------- markdown mirror
def render_markdown(data: dict, base_url: str) -> str:
    site = data["site"]
    brand = data["brand"]
    snapshot = data["snapshot"]
    metrics = compute(data)
    page_url = base_url or "index.html"

    lines: list[str] = []
    lines.append(f"# {site['title']}")
    lines.append("")
    lines.append(f"> 数据快照 {snapshot['collected_at']} · 公开发布 {snapshot['published_at']} · v{data['version']}")
    lines.append(f"> 数据许可：{site['license_data']}（{site['license_data_url']}） · 代码许可：{site['license_code']}")
    lines.append(f"> 在线页面：{page_url}")
    lines.append(f"> 开放数据：{page_url.rstrip('/')}/data/geo-report.json" if base_url else "> 开放数据：data/geo-report.json")
    lines.append("")
    lines.append("## 摘要")
    lines.append("")
    lines.append(f"- 品牌提及率：{metrics['mentioned']} / {metrics['total_queries']} = {metrics['mention_rate']:.0f}%")
    lines.append(f"- 域名引用率：{metrics['cited']} / {metrics['total_queries']} = {metrics['domain_rate']:.0f}%")
    lines.append(f"- 站点可读性：{metrics['audit_pass']} / {metrics['audit_total']} 项通过")
    lines.append(f"- 竞品被推荐：{metrics['brands_total']} 家次，平均每问 {metrics['brands_avg']:.1f} 家")
    lines.append(f"- 内容资产：{metrics['asset_count']} 项（含 {metrics['faq_count']} 条 FAQ）")
    lines.append("")
    lines.append("## 一、AI 搜索检测结果")
    lines.append("")
    lines.append("| # | 问题 | AI 推荐品牌 | 合一自动化 |")
    lines.append("|---|---|---|---|")
    for index, query in enumerate(data["queries"], start=1):
        lines.append(
            f"| {index} | {query['question']} | {'、'.join(query['brands'])}（{len(query['brands'])} 家） | "
            f"{'已提及' if query['brand_mentioned'] else '未出现'} |"
        )
    lines.append("")
    for index, query in enumerate(data["queries"], start=1):
        lines.append(f"### 问题 {index}：{query['question']}")
        lines.append("")
        lines.append(f"**AI 推荐品牌（{len(query['brands'])} 家）：** {'、'.join(query['brands'])}")
        lines.append("")
        lines.append("**AI 原回答：**")
        lines.append("")
        lines.append(query["answer"])
        lines.append("")
    lines.append("## 二、站点机器可读性审计")
    lines.append("")
    lines.append("| 检查项 | 状态 | 现状 | 修复建议 |")
    lines.append("|---|---|---|---|")
    for check in data["audit"]["checks"]:
        status = "通过" if check["status"] == "pass" else "未通过"
        lines.append(f"| {check['title']} | {status} | {check['detail']} | {check['fix']} |")
    lines.append("")
    lines.append(f"> {data['audit']['summary']}")
    lines.append("")
    lines.append("## 三、已产出的 GEO 内容资产")
    lines.append("")
    for asset in data["assets"]:
        lines.append(f"- **{asset['title']}**（{asset['tag']}）：{asset['desc']}")
    lines.append("")
    lines.append("## 四、改造路线图")
    lines.append("")
    for step in data["roadmap"]:
        lines.append(f"- **{step['id']} · {step['title']}**（{step['phase']}）：{step['desc']} 验收信号：{step['signal']}")
    lines.append("")
    lines.append("## 五、国内 AI 检索地图")
    lines.append("")
    lines.append("| 国内 AI | 背后检索源 | 优先投放渠道 | 见效周期 |")
    lines.append("|---|---|---|---|")
    for channel in data["channels"]:
        lines.append(
            f"| {channel['ai']}（{channel['vendor']}） | {channel['source']} | {'、'.join(channel['channels'])} | {channel['period']} |"
        )
    lines.append("")
    lines.append(f"> {data['insight']}")
    lines.append("")
    lines.append("## 六、现状警示")
    lines.append("")
    for risk in data["risks"]:
        lines.append(f"- **{risk['title']}**（风险 {risk['severity']}）：{risk['desc']}")
    lines.append("")
    lines.append("## 七、FAQ 知识库")
    lines.append("")
    for category in data["faq"]["categories"]:
        lines.append(f"### {category['name']}")
        lines.append("")
        for item in data["faq"]["items"]:
            if item["category"] != category["id"]:
                continue
            lines.append(f"**{item['id'].upper()} {item['q']}**")
            lines.append("")
            lines.append(item["a"])
            lines.append("")
    lines.append("## 八、方法与局限")
    lines.append("")
    lines.append("| 指标 | 判定方式 | 本次结果 |")
    lines.append("|---|---|---|")
    for row in data["method"]["metrics"]:
        lines.append(f"| {row['name']} | {row['definition']} | {row['result']} |")
    lines.append("")
    lines.append("**检测步骤：**")
    lines.append("")
    for index, step in enumerate(data["method"]["steps"], start=1):
        lines.append(f"{index}. {step}")
    lines.append("")
    lines.append("**局限：**")
    lines.append("")
    for item in data["method"]["limitations"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 九、引用")
    lines.append("")
    lines.append("```text")
    lines.append(data["method"]["citation"]["text"].replace("{URL}", page_url))
    lines.append("```")
    lines.append("")
    lines.append("```bibtex")
    lines.append(data["method"]["citation"]["bibtex"].replace("{URL}", page_url))
    lines.append("```")
    lines.append("")
    lines.append("## 十、建议与修订")
    lines.append("")
    lines.append("任何人均可提交数据修正、内容补充或体验建议。建议进入审核队列，采纳后直接更新数据、重新构建并记录。")
    lines.append("")
    lines.append(f"提交入口：{page_url}#feedback" if base_url else "提交入口：index.html#feedback")
    lines.append("")
    accepted = load_accepted_suggestions()
    if accepted.get("items"):
        lines.append("### 已采纳")
        lines.append("")
        for item in accepted["items"]:
            lines.append(
                f"- **[{item['type']}] {item['title']}**（{item['date']}，来源：{item['submitted_by']}，"
                f"v{item['version']}）：{item['summary']}"
            )
    else:
        lines.append("暂无公开采纳记录。")
    lines.append("")
    lines.append(f"站点品牌：{brand['name']}（{brand['domain']}） · {brand['positioning']}")
    lines.append("")
    return "\n".join(lines)


def render_llms(data: dict, base_url: str) -> str:
    site = data["site"]
    metrics = compute(data)
    prefix = base_url or "./"
    repo = (site.get("repo_url") or "").strip()
    lines = [
        f"# {site['short_name']} · {data['brand']['name']}",
        "",
        f"> {site['description']}",
        "",
        "## 核心事实",
        f"- 快照日期：{data['snapshot']['collected_at']}",
        f"- 检测问题：{metrics['total_queries']} 个",
        f"- 品牌提及：{metrics['mentioned']} 次；域名引用：{metrics['cited']} 次",
        f"- 竞品被推荐：{metrics['brands_total']} 家次",
        f"- 站点可读性：{metrics['audit_pass']}/{metrics['audit_total']} 项通过",
        f"- FAQ：{metrics['faq_count']} 条",
        f"- 数据许可：{site['license_data']}；代码许可：{site['license_code']}",
        "",
        "## 主要资源",
        f"- [仪表盘（HTML）]({prefix})：图表、审计、30 条 FAQ 与引用格式。",
        f"- [完整开放数据（JSON）]({prefix}data/geo-report.json)：本页全部结构化数据。",
        f"- [FAQ 结构化数据（JSON-LD）]({prefix}data/faq-schema.json)：schema.org FAQPage。",
        f"- [Markdown 全文]({prefix}index.md)：适合大模型检索与引用的纯文本版本。",
        f"- [方法说明]({prefix}#method)：指标定义、采样方法与局限。",
        f"- [建议与修订]({prefix}#feedback)：提交修改建议、查看已采纳记录与审核流程。",
    ]
    if base_url:
        lines.append(f"- [站点地图]({prefix}sitemap.xml)")
    if repo:
        lines.extend(["", "## 可选", f"- [源代码仓库]({repo})：构建脚本、模板、样式与数据。"])
    lines.append("")
    return "\n".join(lines)


def render_sitemap(data: dict, base_url: str) -> str:
    lastmod = data["snapshot"]["published_at"]
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "  <url>\n"
        f"    <loc>{esc(base_url)}</loc>\n"
        f"    <lastmod>{esc(lastmod)}</lastmod>\n"
        "    <changefreq>monthly</changefreq>\n"
        "    <priority>1.0</priority>\n"
        "  </url>\n"
        "</urlset>\n"
    )


def render_robots(data: dict, base_url: str) -> str:
    lines = [
        "# GEO 可视化仪表盘 · 合一自动化",
        "# 本页公开数据，明确欢迎搜索引擎与 AI 检索代理抓取。",
        "",
        "User-agent: *",
        "Allow: /",
        "",
    ]
    for bot in [
        "GPTBot",
        "OAI-SearchBot",
        "ChatGPT-User",
        "ClaudeBot",
        "anthropic-ai",
        "PerplexityBot",
        "Googlebot",
        "Google-Extended",
        "Applebot-Extended",
        "Bingbot",
        "Baiduspider",
        "Sogou web spider",
        "YisouSpider",
        "Bytespider",
    ]:
        lines.extend([f"User-agent: {bot}", "Allow: /", ""])
    if base_url:
        lines.append(f"Sitemap: {base_url}sitemap.xml")
    else:
        lines.append("# 设置 base_url 后会自动写入 Sitemap 地址。")
    lines.append("")
    return "\n".join(lines)


def render_faq_schema(data: dict, base_url: str) -> str:
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "name": "合一自动化 FAQ 知识库",
        "description": f"{data['brand']['name']} 的 {len(data['faq']['items'])} 条 GEO FAQ，覆盖工业读码器、机器视觉、传感器与锂电追溯。",
        "inLanguage": data["site"]["lang"],
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
            }
            for item in data["faq"]["items"]
        ],
    }
    if base_url:
        schema["url"] = base_url + "#faq"
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"


# --------------------------------------------------------------------------- render page
def render_page(data: dict, base_url: str, files: dict[str, str]) -> str:
    site = data["site"]
    brand = data["brand"]
    snapshot = data["snapshot"]
    metrics = compute(data)
    template = TEMPLATE_FILE.read_text(encoding="utf-8")

    faq_filters, faq_groups = render_faq(data)
    method_metrics, method_steps, limitations, changelog = render_method(data)

    citation_text = data["method"]["citation"]["text"].replace(
        "{URL}", base_url or "index.html"
    )
    citation_bibtex = data["method"]["citation"]["bibtex"].replace(
        "{URL}", base_url or "index.html"
    )

    sizes = {name: max(1, round(len(content.encode("utf-8")) / 1024)) for name, content in files.items()}
    downloads = [
        ("data/geo-report.json", "geo-report.json", sizes.get("geo-report.json", 32)),
        ("data/faq-schema.json", "faq-schema.json", sizes.get("faq-schema.json", 8)),
        ("index.md", "index.md", sizes.get("index.md", 40)),
        ("llms.txt", "llms.txt", sizes.get("llms.txt", 2)),
    ]

    legacy = snapshot.get("legacy", {})
    legacy_note = (
        f"初版仪表盘标注站点可读性 {legacy.get('readability', '2 / 5')}、内容资产 {legacy.get('assets', 36)}；"
        f"本页按 {metrics['audit_total']} 项检测与 {metrics['asset_count']} 项资产清单重新核算，"
        "原始数值保留在开放数据的 <code>snapshot.legacy</code> 字段中。"
    )

    accepted = load_accepted_suggestions()
    accepted_items = accepted.get("items", [])
    repo_url = (site.get("repo_url") or "").strip()

    replacements = {
        "SITE_TITLE": esc(site["title"]),
        "SITE_DESCRIPTION": attr(site["description"]),
        "SITE_AUTHOR": attr(site["author"]),
        "SITE_KEYWORDS": attr(",".join(site["keywords"])),
        "SITE_SHORT_NAME": esc(site["short_name"]),
        "OG_IMAGE": attr((base_url + "assets/og-cover.png") if base_url else "assets/og-cover.png"),
        "HEAD_EXTRA": render_head_extra(data, base_url),
        "NAV_LINKS": render_nav_links(),
        "MOBILE_NAV_LINKS": render_mobile_nav(),
        "FOOTER_NAV_LINKS": render_footer_nav(),
        "REPO_LINK": render_repo_link(data),
        "SNAPSHOT_DATE": esc(snapshot["collected_at"]),
        "PUBLISHED_DATE": esc(snapshot["published_at"]),
        "VERSION": esc(data["version"]),
        "TOTAL_BRANDS": str(metrics["brands_total"]),
        "MENTION_DISPLAY": str(metrics["mentioned"]),
        "QUOTE": esc(data["hero"]["quote"]),
        "QUOTE_QUESTION": "1",
        "KPI_CARDS": render_kpis(data, metrics),
        "GAP_ROWS": render_gap_rows(data),
        "ANSWER_ITEMS": render_answers(data),
        "COMPETITOR_ROWS": render_competitor_rows(data),
        "AUDIT_PASS": str(metrics["audit_pass"]),
        "AUDIT_TOTAL": str(metrics["audit_total"]),
        "AUDIT_SUMMARY": esc(data["audit"]["summary"]),
        "AUDIT_CARDS": render_audit_cards(data, metrics),
        "ASSET_COUNT": str(metrics["asset_count"]),
        "ASSET_CARDS": render_asset_cards(data),
        "ROADMAP_ITEMS": render_roadmap(data),
        "CHANNEL_ROWS": render_channel_rows(data),
        "INSIGHT": esc(data["insight"]),
        "RISK_CARDS": render_risk_cards(data),
        "FAQ_COUNT": str(metrics["faq_count"]),
        "FAQ_FILTERS": faq_filters,
        "FAQ_GROUPS": faq_groups,
        "METHOD_METRICS": method_metrics,
        "METHOD_STEPS": method_steps,
        "LIMITATIONS": limitations,
        "LEGACY_NOTE": legacy_note,
        "CHANGELOG": changelog,
        "DATA_LICENSE": esc(site["license_data"]),
        "LICENSE_DATA_URL": attr(site["license_data_url"]),
        "REPO_URL_OR_LICENSE": "LICENSE",
        "CODE_LICENSE": esc(site["license_code"]),
        "CITATION_TEXT": esc(citation_text),
        "CITATION_BIBTEX": esc(citation_bibtex),
        "DOWNLOAD_CARDS": render_downloads(downloads),
        "YEAR": snapshot["published_at"][:4],
        "BRAND_NAME": esc(brand["name"]),
        "REPO_URL": attr(repo_url),
        "ACCEPTED_COUNT": str(len(accepted_items)),
        "ACCEPTED_ITEMS": render_accepted_items(accepted),
    }

    page = template
    for key, value in replacements.items():
        page = page.replace("{{" + key + "}}", value)

    leftovers = re.findall(r"\{\{[A-Z0-9_]+\}\}", page)
    if leftovers:
        raise ValueError("Unreplaced template tokens: " + ", ".join(sorted(set(leftovers))))
    return page


# --------------------------------------------------------------------------- validation
class DocumentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.append(attributes["id"])
        if tag == "a" and attributes.get("href"):
            self.hrefs.append(attributes["href"])


def validate(data: dict, page: str, base_url: str, expected_files: set[str] | None = None) -> None:
    metrics = compute(data)
    assert metrics["faq_count"] == 30, "expected 30 FAQ entries"
    assert metrics["total_queries"] == 5, "expected 5 queries"
    assert metrics["mentioned"] == 0 and metrics["cited"] == 0, "snapshot should be zero mentions"

    accepted = load_accepted_suggestions()
    for item in accepted.get("items", []):
        for key in ("id", "date", "type", "title", "summary", "submitted_by", "version"):
            if not item.get(key):
                raise ValueError(f"accepted suggestion {item.get('id', '?')} is missing {key}")
        if "contact" in item:
            raise ValueError("accepted suggestions must not publish contact details")

    parser = DocumentParser()
    parser.feed(page)
    duplicates = {item for item in parser.ids if parser.ids.count(item) > 1}
    if duplicates:
        raise ValueError("Duplicate element ids: " + ", ".join(sorted(duplicates)))

    ids = set(parser.ids)
    broken = [href for href in parser.hrefs if href.startswith("#") and len(href) > 1 and href[1:] not in ids]
    if broken:
        raise ValueError("Broken in-page links: " + ", ".join(sorted(set(broken))))

    local_files = []
    for href in parser.hrefs:
        if re.match(r"^(https?:|mailto:|#|data:)", href):
            continue
        local_files.append(href.split("#")[0].split("?")[0])
    expected = expected_files or set()
    missing = [
        item for item in set(local_files)
        if item and item not in expected and not (ROOT / item).exists()
    ]
    if missing:
        raise ValueError("Missing local files referenced by the page: " + ", ".join(sorted(missing)))

    schemas = re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
    if not schemas:
        raise ValueError("No JSON-LD found")
    for schema in schemas:
        json.loads(schema.replace("<\\/", "</"))

    if base_url and base_url not in page:
        raise ValueError("Base URL missing from rendered page")
    if len(page) < 40_000:
        raise ValueError("Rendered page looks unexpectedly small")


# --------------------------------------------------------------------------- build
def normalize_base(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url):
        raise ValueError("base URL must start with http:// or https://")
    if not url.endswith("/"):
        url += "/"
    return url


def build(args: argparse.Namespace) -> dict[str, str]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    base_url = normalize_base(args.base_url or data["site"].get("base_url") or "")

    # Generate machine-readable exports first so download sizes are accurate.
    faq_schema = render_faq_schema(data, base_url)
    markdown = render_markdown(data, base_url)
    llms = render_llms(data, base_url)
    files_for_sizes = {
        "geo-report.json": DATA_FILE.read_text(encoding="utf-8"),
        "faq-schema.json": faq_schema,
        "index.md": markdown,
        "llms.txt": llms,
    }

    page = render_page(data, base_url, files_for_sizes)

    outputs: dict[str, str] = {
        "index.html": page,
        "index.md": markdown,
        "llms.txt": llms,
        "robots.txt": render_robots(data, base_url),
        "data/faq-schema.json": faq_schema,
    }
    if base_url:
        outputs["sitemap.xml"] = render_sitemap(data, base_url)

    validate(data, page, base_url, set(outputs))

    if args.check:
        stale = []
        for name, content in outputs.items():
            path = ROOT / name
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(name)
        if stale:
            print("Generated files are stale:", ", ".join(stale), file=sys.stderr)
            print("Run: python scripts/build.py" + (f" --base-url {base_url}" if base_url else ""), file=sys.stderr)
            raise SystemExit(1)
        print(f"All {len(outputs)} generated files are up to date.")
        return outputs

    for name, content in outputs.items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    if not base_url:
        stale_sitemap = ROOT / "sitemap.xml"
        if stale_sitemap.exists():
            stale_sitemap.unlink()
            print("Removed sitemap.xml because base_url is not configured.")

    print(f"Built {len(outputs)} files for {len(data['queries'])} queries / {len(data['faq']['items'])} FAQ.")
    if base_url:
        print(f"Canonical base URL: {base_url}")
    else:
        print("WARNING: site.base_url is empty; canonical, og:url and sitemap.xml were skipped.")
        print("         Pass --base-url https://your-domain/ before deploying.")
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the open GEO dashboard.")
    parser.add_argument("--base-url", default="", help="Absolute public URL, e.g. https://example.com/geo/")
    parser.add_argument("--check", action="store_true", help="Verify generated files are current; do not write")
    args = parser.parse_args(argv)
    try:
        build(args)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
