# -*- coding: utf-8 -*-
"""One-off importer: build data/geo-report.json from the original workspace files."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT / "geo-dashboard"
report = json.loads((ROOT / "geo_report.json").read_text(encoding="utf-8"))
faq_md = (ROOT / "FAQ知识库-合一自动化.md").read_text(encoding="utf-8")

# ---------------------------------------------------------------- FAQ parser
CATEGORY_MAP = {
    "工业读码器": ("reader", "工业读码器"),
    "机器视觉": ("vision", "机器视觉与视觉检测"),
    "传感器": ("sensor", "传感器"),
    "锂电池追溯读码": ("battery", "锂电池追溯读码"),
}
faq_items = []
current_cat = None
for line in faq_md.splitlines():
    if line.startswith("## "):
        for key, (cid, _) in CATEGORY_MAP.items():
            if key in line:
                current_cat = cid
                break
    m = re.match(r"\*\*Q(\d+):(.*?)\*\*\s*$", line.strip())
    if m and current_cat:
        faq_items.append({
            "id": f"q{int(m.group(1))}",
            "category": current_cat,
            "q": m.group(2).strip(),
            "a": "",
        })
    elif faq_items and line.startswith("A:") and not faq_items[-1]["a"]:
        faq_items[-1]["a"] = line[2:].strip()
    elif (faq_items and faq_items[-1]["a"] and line.strip()
          and not line.startswith(("#", "**Q", "---"))):
        faq_items[-1]["a"] += "\n" + line.strip()

assert len(faq_items) == 30, len(faq_items)
assert all(item["a"] for item in faq_items), "some FAQ answer missing"
counts = {}
for item in faq_items:
    counts[item["category"]] = counts.get(item["category"], 0) + 1
assert counts == {"reader": 10, "vision": 10, "sensor": 5, "battery": 5}, counts

# ------------------------------------------------------------- query mapping
META = {
    "q1": ("工业读码器厂家", ["海康机器人", "新大陆", "研祥金码", "斯普锐", "微图视觉"]),
    "q2": ("机器视觉供应商", ["华汉伟业", "征图新视", "凌云光", "天准", "矩子", "海康机器人", "奥普特", "基恩士", "康耐视"]),
    "q3": ("工业视觉方案", ["华汉伟业", "天准", "凌云光", "征图新视"]),
    "q4": ("激光位移传感器", ["深视智能", "奥普特", "无锡泓川", "基恩士", "欧姆龙", "松下", "Micro-Epsilon"]),
    "q5": ("锂电池追溯读码", ["奥普特", "海康机器人", "研祥金码", "康耐视"]),
}
queries = []
for index, result in enumerate(report["results"], start=1):
    qid = f"q{index}"
    short, brands = META[qid]
    assert result["question"] == [
        "国内有哪些工业读码器厂家?",
        "机器视觉检测系统供应商有哪些?",
        "工业视觉检测解决方案哪家好?",
        "激光位移传感器品牌有哪些?",
        "锂电池追溯读码方案哪家做得好?",
    ][index - 1]
    queries.append({
        "id": qid,
        "question": result["question"],
        "short": short,
        "brands": brands,
        "brand_mentioned": bool(result["analysis"]["mentioned"]),
        "domain_cited": bool(result["analysis"]["domain_cited"]),
        "answer": result["answer"].strip(),
    })

assert sum(len(q["brands"]) for q in queries) == 29

data = {
    "version": "1.0.0",
    "site": {
        "lang": "zh-CN",
        "title": "GEO 可视化仪表盘 · 合一自动化 AI 搜索可见性公开报告",
        "short_name": "GEO 开放仪表盘",
        "description": "公开的 GEO 检测报告：5 个工业视觉核心问题在 AI 搜索中的品牌提及率与域名引用率均为 0%；附站点机器可读性审计、30 条 FAQ 知识库与可下载的开放数据。",
        "base_url": "",
        "repo_url": "",
        "author": "合一自动化",
        "license_data": "CC BY 4.0",
        "license_data_url": "https://creativecommons.org/licenses/by/4.0/",
        "license_code": "MIT",
        "keywords": [
            "GEO", "生成式引擎优化", "AI 搜索", "品牌提及率", "工业读码器",
            "机器视觉", "激光位移传感器", "锂电池追溯", "合一自动化",
        ],
    },
    "brand": {
        "name": "合一自动化",
        "legal_name": "广东合一自动化科技有限公司",
        "aliases": ["广东合一自动化", "合一自动化科技", "合一", "Heyi", "VISIONHY", "visionheyi"],
        "domain": "visionheyi.com",
        "url": "https://www.visionheyi.com/",
        "address": {"region": "广东省", "locality": "深圳市光明区"},
        "positioning": "工业读码器 · 机器视觉检测 · 传感器与锂电追溯方案",
        "description": "专注机器工业视觉，提供工业读码器、视觉检测系统、激光位移传感器等核心零部件与解决方案，重点服务新能源锂电、3C 电子、汽车零部件等行业。",
    },
    "snapshot": {
        "collected_at": "2026-10-31",
        "published_at": "2026-11-11",
        "method": "联网 AI 搜索首轮回答 + 关键词匹配 + 人工复核",
        "model_note": "原始记录未标注具体模型与平台版本",
        "legacy": {
            "readability": "2 / 5",
            "assets": 36,
            "note": "初版仪表盘的两处计数与明细不一致；本页按检测项与资产清单重新核算为 2 / 6 与 38 项，原始数值保留于此。",
        },
    },
    "hero": {
        "quote": "国内做工业读码器的厂家，可以先了解这几家（按厂商列举，不是排名）：海康机器人、新大陆自动识别、研祥金码、苏州斯普锐、杭州微图视觉。",
        "quote_question": "国内有哪些工业读码器厂家?",
    },
    "kpis": [
        {
            "key": "mention_rate",
            "label": "品牌提及率",
            "tone": "danger",
            "icon": "mention",
            "note": "5 个核心问题 · 0 次被提及",
            "hint": "回答中出现任一品牌关键词的问题占比",
        },
        {
            "key": "domain_rate",
            "label": "域名引用率",
            "tone": "danger",
            "icon": "link",
            "note": "visionheyi.com · 0 次被引用",
            "hint": "回答中引用本站链接的问题占比",
        },
        {
            "key": "audit_rate",
            "label": "站点可读性",
            "tone": "warn",
            "icon": "shield",
            "note": "robots / sitemap 通过；H1 / Schema / llms.txt / 知识页缺失",
            "hint": "6 项机器可读性检查的通过项",
        },
        {
            "key": "asset_count",
            "label": "内容资产",
            "tone": "success",
            "icon": "layers",
            "note": "30 条 FAQ + 4 份文档 + 3 个工具 + 1 份 Schema",
            "hint": "已产出的可公开内容单元",
        },
    ],
    "queries": queries,
    "audit": {
        "checks": [
            {
                "id": "robots", "title": "robots.txt 放行 AI 爬虫", "status": "pass",
                "detail": "Allow: / · 未发现 Disallow",
                "fix": "保持现状；新增拦截规则后复查。",
            },
            {
                "id": "sitemap", "title": "sitemap.xml 站点地图", "status": "pass",
                "detail": "已提供站点地图",
                "fix": "新增页面后同步更新。",
            },
            {
                "id": "h1", "title": "首页 H1 标题", "status": "fail",
                "detail": "0 个 H1，标题层级从 H2 开始",
                "fix": "首屏加唯一 H1，含「工业读码器 / 机器视觉」主词。",
            },
            {
                "id": "schema", "title": "Schema 结构化数据", "status": "fail",
                "detail": "0 个 JSON-LD，AI 难以识别页面类型",
                "fix": "至少部署 Organization、Product、FAQPage 三类。",
            },
            {
                "id": "llms", "title": "llms.txt 站点说明书", "status": "fail",
                "detail": "404 不存在，缺少给大模型的入口",
                "fix": "根目录新增 llms.txt，列核心页面与一句话介绍。",
            },
            {
                "id": "content", "title": "知识型内容结构", "status": "fail",
                "detail": "以产品目录为主，缺方案 / FAQ / 案例",
                "fix": "建立方案、FAQ、案例三类知识页并互相链接。",
            },
        ],
        "summary": "网站允许 AI 来抓，但没有给出足够多值得抓、值得引用、值得推荐的内容。",
    },
    "assets": [
        {"title": "GEO 教程", "desc": "从 SEO 到 GEO 的完整方法论，6 大策略", "tag": "方法论", "icon": "book"},
        {"title": "诊断与改造方案", "desc": "技术审计 + 三阶段整改计划 + Schema 模板", "tag": "策略", "icon": "target"},
        {"title": "锂电全工序方案文章", "desc": "答案优先结构，可直接发布官网", "tag": "内容", "icon": "doc"},
        {"title": "30 条 FAQ 知识库", "desc": "覆盖三大产品线 + 锂电追溯场景", "tag": "内容", "icon": "chat", "href": "#faq"},
        {"title": "FAQPage Schema", "desc": "30 条结构化数据，可直接嵌入网页", "tag": "技术", "icon": "braces", "href": "data/faq-schema.json"},
        {"title": "竞品差距分析", "desc": "基于实测 AI 回答，含可复制打法", "tag": "分析", "icon": "chart"},
        {"title": "geo_monitor.py", "desc": "品牌提及率 / 域名引用率检测工具", "tag": "工具", "icon": "code"},
        {"title": "site_audit.py", "desc": "站点机器可读性审计工具", "tag": "工具", "icon": "code"},
        {"title": "build_faq_schema.py", "desc": "FAQ → Schema JSON 自动生成", "tag": "工具", "icon": "code"},
    ],
    "roadmap": [
        {
            "id": "P0", "phase": "1~2 周", "title": "技术地基",
            "desc": "修复首页 H1；部署 Organization / Product / FAQPage Schema；上线 llms.txt。",
            "signal": "AI 能准确识别品牌与业务；结构化数据通过校验。",
        },
        {
            "id": "P1", "phase": "1~2 个月", "title": "行业方案文章",
            "desc": "发布《锂电池全工序追溯读码方案详解》，按极片 / 电芯 / 模组 / PACK 拆 4 篇子文章。",
            "signal": "5 个目标问题中至少 1 个出现品牌或域名引用。",
        },
        {
            "id": "P2", "phase": "2~3 个月", "title": "FAQ 与结构化问答",
            "desc": "部署 30 条 FAQ（本页已公开）并上线 FAQPage Schema，按用户真实提问持续扩充。",
            "signal": "FAQ 页面被检索或引用；品牌提及率开始非零。",
        },
        {
            "id": "P3", "phase": "3~6 个月", "title": "真实项目案例",
            "desc": "整理 3~5 个脱敏案例，按「问题 → 方案 → 效果」结构写作，附读码率与节拍数据。",
            "signal": "案例页获得外部链接与 AI 引用。",
        },
        {
            "id": "P4", "phase": "3~6 个月", "title": "站外品牌实体",
            "desc": "百度百科 / 头条号 / 知乎机构号 / 公众号 + 行业媒体背书，统一全网品牌描述。",
            "signal": "AI 回答中出现品牌实体，而不只是官网链接。",
        },
    ],
    "channels": [
        {"ai": "豆包", "vendor": "字节", "source": "头条搜索 / 抖音生态", "channels": ["今日头条号", "抖音", "百度百科"], "period": "1~2 月"},
        {"ai": "通义千问", "vendor": "阿里", "source": "夸克搜索 / 阿里生态", "channels": ["知乎机构号", "夸克百科", "百家号"], "period": "1~2 月"},
        {"ai": "文心一言", "vendor": "百度", "source": "百度搜索", "channels": ["百度百科", "百家号", "百度知道"], "period": "1~2 月"},
        {"ai": "Kimi", "vendor": "月之暗面", "source": "自有搜索（多源）", "channels": ["知乎", "百科", "高质量网页"], "period": "2~4 月"},
        {"ai": "DeepSeek", "vendor": "深度求索", "source": "自有搜索", "channels": ["知乎", "技术站", "高质量网页"], "period": "2~4 月"},
        {"ai": "腾讯元宝", "vendor": "腾讯", "source": "搜狗 / 微信生态", "channels": ["微信公众号", "搜狗百科"], "period": "2~4 月"},
    ],
    "insight": "国内 AI 各自绑定自家搜索引擎——想让豆包推荐，先让头条 / 抖音收录；想让文心推荐，先让百度百科 / 百家号收录；想让千问推荐，先让知乎 / 夸克收录。",
    "risks": [
        {
            "title": "已有内容集中在低权重 B2B 平台", "severity": "高",
            "desc": "cnpinpai.cn、wancili.com、义乌网等平台有 FAQ / 案例 / 数据，但平台权重低，国内 AI 不一定采信。",
        },
        {
            "title": "缺「品牌实体」", "severity": "高",
            "desc": "没有百度百科词条等公开实体信息，国内 AI 难以把「合一自动化」识别为独立可信实体。",
        },
        {
            "title": "未进入各 AI 的核心检索源", "severity": "中",
            "desc": "今日头条、知乎、百家号等 AI 高频采信渠道尚未布局。",
        },
    ],
    "faq": {
        "categories": [
            {"id": "reader", "name": "工业读码器", "desc": "选型、DPM 码、接口与维护"},
            {"id": "vision", "name": "机器视觉与视觉检测", "desc": "2D/3D、深度学习与项目落地"},
            {"id": "sensor", "name": "传感器", "desc": "激光位移、颜色识别与测量"},
            {"id": "battery", "name": "锂电池追溯读码", "desc": "全工序追溯与高速读码"},
        ],
        "items": faq_items,
    },
    "method": {
        "metrics": [
            {"name": "品牌提及率", "definition": "回答中出现任一品牌关键词的问题数 ÷ 问题总数", "result": "0 / 5 = 0%"},
            {"name": "域名引用率", "definition": "回答引用 visionheyi.com 任一链接的问题数 ÷ 问题总数", "result": "0 / 5 = 0%"},
            {"name": "站点可读性", "definition": "6 项机器可读性检查中通过的项数", "result": "2 / 6"},
            {"name": "内容资产", "definition": "已产出的 FAQ 条目 + 文档 + 工具 + 结构化数据文件", "result": "38 项"},
        ],
        "steps": [
            "确定 5 个核心业务问题，覆盖读码器、视觉系统、视觉方案、激光位移传感器、锂电追溯五类采购意图。",
            "通过联网 AI 搜索逐题提问，记录首轮回答原文与答案内链接；原始回答可在本页逐条展开。",
            "用品牌别名（合一自动化 / 广东合一自动化 / 合一 / Heyi / VISIONHY / visionheyi）与域名 visionheyi.com 做关键词匹配，统计提及与引用。",
            "用 site_audit.py 与人工复查检查 robots.txt、sitemap.xml、H1、JSON-LD、llms.txt 与内容结构。",
        ],
        "limitations": [
            "本页是 2026-10-31 的一次快照，AI 回答会随模型版本、时间和联网结果变化。",
            "原始记录未标注具体模型 / 平台；不同后端可能给出不同结果。",
            "5 个问题是最小样本，适合定位问题，不代表完整市场份额。",
            "关键词匹配可能漏掉未写全称的品牌提及，人工复核可降低误差。",
            "站点审计为脚本 + 人工判断结果，页面改版后需重新检测。",
        ],
        "citation": {
            "text": "合一自动化. GEO 可视化仪表盘：合一自动化 AI 搜索可见性公开报告（2026-10-31 快照）[DS/OL]. 2026-11-11. {URL}.",
            "bibtex": "@misc{heyi_geo_dashboard_2026,\n  title   = {GEO 可视化仪表盘：合一自动化 AI 搜索可见性公开报告},\n  author  = {{合一自动化}},\n  year    = {2026},\n  month   = {11},\n  note    = {数据快照 2026-10-31},\n  url     = {{{URL}}},\n  license = {CC BY 4.0}\n}",
        },
    },
    "changelog": [
        {"date": "2026-11-11", "text": "公开发布 v1.0：新增全文检索、FAQ 知识库、开放数据下载与机器可读输出；站点可读性由 2/5 修正为 2/6、内容资产由 36 修正为 38。"},
        {"date": "2026-10-31", "text": "完成 5 个核心问题的 AI 搜索检测与站点审计，产出初版可视化仪表盘。"},
    ],
}

out = REPO / "data" / "geo-report.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("wrote", out, out.stat().st_size, "bytes;", len(faq_items), "FAQ;", len(queries), "queries")
