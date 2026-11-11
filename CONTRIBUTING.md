# 参与贡献

感谢你帮助这份公开的 GEO 报告变得更准确、更好用。你可以提交数据修正、补充 FAQ、改进可访问性，或直接改代码。

## 一、提交建议（不需要会写代码）

- 页面右上角「提建议」；
- 或在 GitHub 仓库的 **Issues → 新建 Issue → 修改建议** 中填写模板。

数据类建议请附**可公开核对的来源链接**（官网、标准、公开报告）。请勿提交个人隐私、商业秘密或攻击性内容。

## 二、修改代码或数据

```bash
git clone <your-fork>
cd geo-dashboard

python scripts/build.py          # 重新生成 index.html / index.md / llms.txt / ...
python scripts/serve.py          # 本地预览 + 建议 API
python scripts/build.py --check  # 确认生成文件与提交一致（不写文件）
```

### 约定

- **只使用 Python 标准库**构建；不要引入前端框架、CDN 或远程字体。
- 页面正文必须在 HTML 中直出，搜索、主题、建议表单等交互只做渐进增强。
- 数据以 `data/geo-report.json` 为唯一来源；改完数据要重新构建，不要手改 `index.html`。
- FAQ 增删后同步更新分类计数；`id` 使用 `q1`、`q2` 这类稳定值。
- 修改快照数据时注明采集日期、方法与局限；如果是计数勘误，把旧值保留在 `snapshot.legacy`。
- 保持中文文案简洁、可核对；不要写没有来源的效果承诺。
- 不要提交 `GEO_SUGGEST_DIR` 里的私有收件箱、`.env`、API key 或证书。

### 提交前自检

```bash
python scripts/build.py --check
python -m py_compile scripts/*.py
```

- 桌面与移动端各看一次；
- 用键盘 Tab 走一遍表单与 FAQ；
- 确认暗色/亮色主题都正常；
- 确认没有在页面中泄露联系方式。

## 三、采纳建议的流程

维护者与 AI 助手依据 [docs/REVIEW.md](docs/REVIEW.md) 审核。采纳后：

1. 修改数据/模板；
2. 提升版本号与发布日期；
3. `python scripts/build.py`；
4. 写入公开记录：

```bash
python scripts/suggestions.py accept SUG-... --title "..." --summary "..." --version 1.1.0
```

5. 提交 PR / 合并并部署。

## 四、许可

提交即表示你同意：代码贡献按 [MIT](LICENSE) 许可，数据与文字贡献按 [CC BY 4.0](DATA-LICENSE.md) 许可。
