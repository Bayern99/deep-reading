# 每日生产 · 构建说明

先读仓库根目录 `FOUNDATION.md`（原则）和 `DESIGN.md`（视觉）。

## 一句话流程

```bash
cd render && python3 build.py --issue YYYY-MM-DD
```

输入：`../<日期>/final.json`（内容定稿）+ `../<日期>/front.json`（头版选稿）
输出：`../<日期>/dist/index.html`

## 前置条件

1. `final.json` 已 QA。渲染器只做排版，一字不改。
2. `front.json` 写好 dek / lead_id / also_ids。缺省时回退 A1 新闻，仍禁止 digest/图注/生活稿当头版。

## 策展数据（不许自动生成）

| 文件 | 用途 |
|---|---|
| `<date>/editorial-plans/<id>.json` | 增强篇；模块必须增加新视角 |
| `render/images.json` | 已验证图片；宁缺毋滥 |
| `render/modules.json` | 遗留三件套；新稿走 editorial-plans |

## 构建后必跑的检查

```bash
cd render && python3 build.py --issue YYYY-MM-DD
```

断言覆盖：条目锚点、段落逐字、无 `text-wrap:pretty`、无 duel。另截 1440/390：头版 + digest + 一篇长文，0 横向溢出。读者表面不得出现流水线字样（见 `FOUNDATION.md`）。

## 新日期期号

1. 产出 `<新日期>/final.json`。
2. 写 `<新日期>/front.json`（dek / lead / also）。
3. 仅当某篇值得模块时，加 `editorial-plans/` 或 `images.json`。
4. `python3 build.py --issue <新日期>`，交付 `dist/index.html`。

## 故障排查

- 段落数对不上 → 查 final.json 的 `body_cn` 是否含异常换行，修内容不修渲染器。
- 表格错位 → data_table 的 `|` 分隔源文本问题，属已知启发式限制（行头合并），数字逐字无误即可。
- 样式漂移 → 对照 `../DESIGN.md` v1.0 数值表与 `reference/hybrid-v3/index.html` 基准页。
