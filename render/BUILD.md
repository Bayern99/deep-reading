# 每日生产 · 构建说明

## 一句话流程

```bash
cd ~/workspace/wsj-deep-read/render && python3 build.py --issue 2026-10-12
```

输入：`../<日期>/final.json`（内容定稿，唯一内容依据）
输出：`../<日期>/dist/index.html`（整期单文件，可直接交付）

## 前置条件（内容管线）

1. `final.json` 必须已通过 QA（提取→结构化→术语表→翻译→QA，按 `~/workspace/skills/deep-read/SKILL.md`）。
2. 渲染器**只做排版**：正文逐字来自定稿，一字不改、不重译、不润色。

## 策展数据（人工维护，不许自动生成）

| 文件 | 用途 | 何时更新 |
|---|---|---|
| `render/modules.json` | 时间线/关键数字/引语（三件套） | 某篇文章需要辅助模块时，由编辑手工整理后加入，以 `final_id` 为 key |
| `render/images.json` | 已验证图片清单（文件+图注+来源） | 有可用的真实图片时加入；宁缺毋滥 |

没有 key 的文章自动降级为干净文章页（标题/导语/正文/底部背景折叠），不会凭空长出模块。

## 构建后必跑的检查

```bash
cd ~/workspace/wsj-deep-read/render && python3 build.py --issue 2026-10-12 --check
```

`--check` 做：117 条锚点计数、每篇段落数与 final.json 对照、中英对数、无 `text-wrap:pretty`、无 duel 残留。
另需人工：playwright 截 1440/768/390（目录+抽查 3 种文章类型），确认 0 横向溢出。

## 新日期期号

1. 按既有管线产出 `<新日期>/final.json`。
2. 如需策展模块/图片，更新 `modules.json` / `images.json`。
3. `python3 build.py --issue <新日期>`，检查后交付 `dist/index.html`。

## 故障排查

- 段落数对不上 → 查 final.json 的 `body_cn` 是否含异常换行，修内容不修渲染器。
- 表格错位 → data_table 的 `|` 分隔源文本问题，属已知启发式限制（行头合并），数字逐字无误即可。
- 样式漂移 → 对照 `../DESIGN.md` v1.0 数值表与 `reference/hybrid-v3/index.html` 基准页。
