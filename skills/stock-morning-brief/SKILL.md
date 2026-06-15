---
name: stock-morning-brief
description: |
  股市早评生成。基于方法论知识库，生成每日早评报告。
  核心：基于一套完整方法论生成每日盘前早报。
  触发词：早评、股市早评、每日早报、morning brief、生成早评
  与其他 skill 的关系：
  - stock-methodology-updater：学习方法论，更新知识库
  - stock-daily-report：收盘日报，数据获取可复用
---

# 股市早评生成 Skill

## 概述

本 Skill 的核心职责是 **使用方法论生成早评报告**。

**核心定位：**
> 读取方法论知识库 → 获取市场数据 → 生成早评报告

**知识库架构：**
```
stock-methodology/                  # 方法论知识库
├── stock_morning_brief_guide.md     # 早报分析方法论主文件
├── stock_morning_brief_templates.md # 早报模板参考
├── stock_selection_guide.md         # 选股方法论
└── manifest.json                   # 版本清单

stock-methodology-updater/    # 更新知识库
stock-morning-brief/        # 使用知识库
```

---

## 环境配置

### 方法论知识库路径

```bash
# 方法论知识库根目录
METHODOLOGY_ROOT=/path/to/Agent-Skills/knowledge-bases/stock-methodology

# 主方法论：$METHODOLOGY_ROOT/stock_morning_brief_guide.md
# 模板参考：$METHODOLOGY_ROOT/stock_morning_brief_templates.md
```

### Python 环境

```bash
PYTHON=/path/to/python3  # 或使用系统Python: python3
```

### 飞书推送配置

```bash
# 接收用户（必须通过环境变量设置，无默认值）
export FEISHU_USER_OPEN_ID=your_feishu_user_open_id_here

# 推送方式：bot 身份 + 禁用代理
# 推送内容：早报摘要（核心数据+市场定调+选股摘要）+ 早报链接 + 股票跟踪链接
```

---

## 快速开始（端到端命令）

```bash
# 完整流程：获取数据 → LLM分析 → 生成报告 → 部署Cloudflare → 推送飞书
cd /path/to/Agent-Skills/skills/stock-morning-brief

# Step 1: 获取市场数据
$PYTHON scripts/fetch_data.py --date 2026-06-15 --output ./tmp/market_data.json

# Step 2: 准备 LLM 分析提示词
$PYTHON scripts/generate_ai_texts.py prepare --data ./tmp/market_data.json --output-dir ./tmp/

# Step 2.5: LLM 分析（Agent 执行）
# 读取 ./tmp/analysis_prompt.md → 输出 ./tmp/llm_analysis.json

# Step 3: 编译 AI 文本
$PYTHON scripts/generate_ai_texts.py compile --data ./tmp/market_data.json --analysis ./tmp/llm_analysis.json --output ./tmp/ai_texts.json

# Step 4: 生成 HTML + 部署 + 推送
$PYTHON scripts/generate_report.py --data ./tmp/market_data.json --ai-texts ./tmp/ai_texts.json --html ./tmp/morning_brief.html --deploy-cloudflare --feishu-push
```

---

## 目录结构

```
stock-morning-brief/              # 对外分发的 SKILL
├── SKILL.md                      # Skill 定义（本文件）
├── requirements.txt              # Python 依赖
├── scripts/
│   ├── fetch_data.py             # 数据获取（国内AKShare优先，国外yfinance优先）
│   ├── generate_ai_texts.py     # AI 文本生成（prepare+compile两步法）
│   ├── generate_report.py        # 报告生成（模板动态填充 + PDF）
│   ├── deploy_to_cloudflare.py   # Cloudflare Pages部署
│   ├── stock_tracker.py          # 入选股票跟踪JSON与独立HTML
│   └── validate_llm_json.py      # LLM输出验证
├── references/
│   └── style_guide.md            # 📋 格式规范
└── templates/
    └── report_template.html      # 报告 HTML 模板（无硬编码数据，全部动态填充）

# 方法论知识库（独立目录，不随 SKILL 附带）
../knowledge-bases/stock-methodology/
├── stock_morning_brief_guide.md      # 📖 早报分析方法论主文件
├── stock_morning_brief_templates.md  # 📖 早报模板参考
├── stock_selection_guide.md          # 📖 选股方法论
└── manifest.json
```

---

## 工作流（四步执行）

### Step 1: 获取市场数据

```bash
$PYTHON scripts/fetch_data.py --date 2026-06-13 --output ./tmp/market_data.json
```

**交易日检查：**
- 脚本会自动检查目标日期是否为交易日（排除周末和主要节假日）
- 非交易日会提示并退出，避免无意义执行
- 使用 `--force` 参数可强制执行

**数据来源优先级（核心规则）：**

| 数据类型 | 优先来源 | 备选来源 | 说明 |
|----------|----------|----------|------|
| A股指数 | **AKShare** | WebSearch | 国内数据优先 AKShare，获取不到标记 `need_websearch` |
| 涨跌家数 | **AKShare** | WebSearch | 通过 `stock_zh_a_spot_em()` 获取 |
| 行业板块 | **AKShare** | WebSearch | 通过 `stock_board_industry_name_em()` 获取 |
| 北向资金 | **AKShare** | WebSearch | 通过 `stock_hsgt_hist_em()` 获取 |
| 两市成交额 | **AKShare** | WebSearch | 通过 `stock_zh_a_spot_em()` 汇总 |
| 美股三大指数 | **yfinance** | WebSearch | ^DJI, ^GSPC, ^IXIC |
| VIX/半导体 | **yfinance** | WebSearch | ^VIX, ^SOX |
| 美股个股 | **yfinance** | WebSearch | NVDA, TSLA 等 |
| 大宗商品 | **yfinance** | WebSearch | CL=F(原油), GC=F(黄金) |
| 全球指数 | **yfinance** | WebSearch | ^N225(日经), ^HSI(恒生) |
| 汇率 | **yfinance** | WebSearch | DX-Y.NYB(美元指数), CNY=X(离岸人民币) |
| 新闻事件 | **WebSearch** | - | 只能通过 WebSearch 获取 |

**脚本逻辑：**
1. 加载 `templates/market_data_template.json` 模板
2. 使用 AKShare 填充 A股数据
3. 使用 yfinance 填充美股数据
4. 填充失败的标记 `need_websearch: true`
5. 输出填充后的 `market_data.json`

### Step 2: 准备 LLM 分析提示词

```bash
$PYTHON scripts/generate_ai_texts.py prepare \
  --data ./tmp/market_data.json \
  --output-dir ./tmp/
```

**输出文件：**
- `./tmp/analysis_prompt.md` — 包含市场数据摘要 + 规则推导结果 + LLM 需分析的字段模板
- `./tmp/ai_texts_rules.json` — 规则推导字段（方向信号、情绪色彩、区间估算）
- `./tmp/event_timeline_auto.html` — 事件时间线 HTML（从数据自动生成）

**脚本自动推导的字段（LLM 无需重复计算）：**

| 字段 | 推导逻辑 |
|------|----------|
| DIRECTION_SIGNAL_CLASS | 指数平均涨幅 > 1.0 → bullish, 0.5~1.0 → neutral-bull |
| DIRECTION_JUDGMENT | 基于指数平均涨幅的文字描述 |
| SENTIMENT_CLASS | avg_pct + up_ratio + limit_up → hot/warm/cold/frozen |
| SH_RANGE_LOW/HIGH | 昨日高点±0.5倍振幅 |

### Step 2.5: LLM 分析（Agent 执行）

**Agent 执行步骤：**
1. 读取 `./tmp/analysis_prompt.md`
2. 基于市场数据 + 方法论进行深度分析
3. 输出 **纯JSON结构化数据** `./tmp/llm_analysis.json`（不含HTML）

> **核心设计原则：脚本管 FORMAT，LLM 管 INSIGHT**
> - LLM 只输出结构化 JSON（评分、文字、逻辑描述）
> - HTML 模板由脚本的 `compile` 命令自动渲染
> - 规则推导字段（方向、情绪、区间）由脚本自动计算

**LLM 输出格式**：详见 `references/style_guide.md`

### Step 3: 编译 AI 文本（脚本自动渲染 HTML）

```bash
$PYTHON scripts/generate_ai_texts.py compile \
  --data ./tmp/market_data.json \
  --analysis ./tmp/llm_analysis.json \
  --output ./tmp/ai_texts.json
```

**compile 做了什么：**
1. 合并规则推导字段（DIRECTION_SIGNAL_CLASS、SENTIMENT_CLASS 等）
2. 将 LLM 的结构化 JSON 转换为 HTML（评分条、卡片、表格、心态管理等）
3. 从 market_data.json 自动生成事件时间线 HTML
4. 输出完整的 `ai_texts.json`（23个字段全部填充）

### Step 4: 生成 HTML 报告并自动部署 Cloudflare

```bash
$PYTHON scripts/generate_report.py \
  --data ./tmp/market_data.json \
  --ai-texts ./tmp/ai_texts.json \
  --html ./tmp/morning_brief_2026-06-13.html \
  --deploy-cloudflare
```

**默认交付规则：**
- 生成 HTML 后自动部署到 Cloudflare Pages
- 最终向用户返回 Cloudflare 公开访问URL
- 不带日期的根路径 `/` 访问最新报告
- 带日期路径 `/YYYY-MM-DD/` 访问指定日期报告
- 同步维护入选股票跟踪 JSON，并发布独立表格页 `/stock-tracker/`
- 用户已完成 `npx wrangler login`，后续无需重复提示登录

**可选参数：**
- `--pdf out.pdf` - 同时生成 PDF
- `--feishu-push` - 自动推送早报摘要到飞书私聊（详见下方"飞书推送说明"）
- `--deploy-cloudflare` - 生成后自动部署到 Cloudflare Pages
- `--cloudflare-project stock-morning-brief` - 指定 Cloudflare Pages 项目名
- `--cloudflare-no-history` - 不按日期保留历史版本
- `--analysis-json ./tmp/llm_analysis.json` - 指定原始分析JSON，用于入选股票跟踪
- `--stock-tracker-json ./data/stock_selection_tracker.json` - 指定股票跟踪JSON
- `--stock-tracker-html ./tmp/stock_tracker.html` - 指定股票跟踪HTML
- `--no-stock-tracker` - 跳过股票跟踪更新

---

### 飞书推送说明（`--feishu-push`）

**推送时机**：HTML 生成后、Cloudflare 部署后（如有）

**推送内容**：
```
📊 **2026-06-15 股市早报**

**📈 核心数据**
- 上证指数：4031.51 (+1.12%)
- 两市成交：32150亿
- 北向资金：净流入86.5亿
- 涨跌家数：3200涨 / 涨停85只

**🎯 市场定调**
指数温和上攻，量能配合，情绪回暖...

**🔥 领涨板块**
- 铜产业链 (+3.2%)
- 锂电池 (+2.8%)
- AI算力 (+2.1%)

**⭐ 精选标的**
- **紫金矿业** (601899) 评分92分
- **天赐材料** (002709) 评分78分
- **工业富联** (601138) 评分75分

---
📎 [查看完整早报](https://stock-morning-brief.pages.dev/)
📈 [入选股票跟踪](https://stock-morning-brief.pages.dev/stock-tracker/)
```

**配置说明**：
- 接收用户：必须通过环境变量 `FEISHU_USER_OPEN_ID` 设置（无默认值）
- 推送身份：bot（`--as bot`）
- 推送时自动禁用代理（`LARK_CLI_NO_PROXY=1`）

---

### Step 5: 入选股票跟踪表

早报生成时自动维护，无需手动执行。详情见下方"入选股票跟踪"章节。

---

```bash
python3 scripts/deploy_to_cloudflare.py \
  --html ./tmp/morning_brief_2026-06-13.html \
  --project stock-morning-brief
```

**功能说明：**
- 将HTML报告部署到Cloudflare Pages，生成公开访问URL
- 支持历史版本保留（默认按日期命名）
- 同时写入根路径和日期路径：
  - 最新报告：`https://stock-morning-brief.pages.dev/`
  - 指定日期：`https://stock-morning-brief.pages.dev/2026-06-13/`
  - 本次部署预览：`https://<deployment-id>.stock-morning-brief.pages.dev/`（可选，不默认返回给用户）

**首次使用配置：**

1. **安装Node.js和wrangler**：
   ```bash
   # 安装wrangler CLI
   npm install -g wrangler

   # 登录Cloudflare账号
   npx wrangler login
   ```

2. **创建Cloudflare Pages项目**：
   - 方式A：首次部署时自动创建（推荐）
   - 方式B：在Cloudflare控制台手动创建

**部署参数：**
- `--html`：HTML文件路径（必需）
- `--project`：Cloudflare Pages项目名（默认：`stock-morning-brief`）
- `--no-history`：不保留历史版本（每次覆盖部署）

**部署结果：**
```json
{
  "cloudflare_url": "https://stock-morning-brief.pages.dev/",
  "latest_url": "https://stock-morning-brief.pages.dev/",
  "dated_url": "https://stock-morning-brief.pages.dev/2026-06-13/",
  "tracker_url": "https://stock-morning-brief.pages.dev/stock-tracker/",
  "deployment_url": "https://<deployment-id>.stock-morning-brief.pages.dev/",
  "deployment_id": "2026-06-13"
}
```

**结合飞书推送（推荐）：**
```bash
# 先部署到Cloudflare，再推送URL到飞书
python3 scripts/deploy_to_cloudflare.py --html report.html > deploy_result.json

# 解析URL并推送到飞书（需配置FEISHU_USER_OPEN_ID环境变量）
```

---

## WebSearch 回退策略

当 AKShare 或 yfinance 获取失败时（标记 `need_websearch: true`），使用 WebSearch 补充：

**搜索关键词模板**：`"{date}" {数据类型} 收盘/涨跌幅/净流入`

| 数据类型 | 关键词示例 |
|----------|-----------|
| A股指数 | `"{date}" 上证指数 收盘 涨跌幅` |
| 北向资金 | `"{date}" 北向资金 净流入` |
| 美股指数 | `"{date}" 道琼斯 纳斯达克 标普500 收盘` |
| 大宗商品 | `"{date}" WTI原油 黄金 价格` |

补充后数据需符合 `market_data.json` 结构，详见 `references/style_guide.md`。

---

## 入选股票跟踪

早报生成时自动维护入选股票跟踪数据：

**数据文件**：
- `data/stock_selection_tracker.json` — 跟踪数据
- `tmp/stock_tracker.html` — 独立表格页面

**JSON字段**：
- `selected_date`：入选日期
- `name/code/market_class`：股票名称、代码、市场
- `reason`：入选原因（10字以内）
- `selected_price`：入选时股价
- `returns.next_day/day_3/day_5/day_7`：次日/3日/5日/7日累计涨跌幅（未到期为 `null`）

**规则**：最多维护 50 只，超过时删除最早加入记录。

**在线访问**：`https://stock-morning-brief.pages.dev/stock-tracker/`

---

## 注意事项

1. **方法论是独立产品**，按版本分发
2. **stock-methodology-updater 不对外分发**，仅自己使用
3. **数据获取失败时**，标记 `need_websearch`，AI Agent 应使用 WebSearch 补充后更新 market_data.json
4. **LLM 分析**：读取 `analysis_prompt.md`，输出结构化 JSON（`llm_analysis.json`），无需 API Key
5. **飞书推送**：需配置 `FEISHU_USER_OPEN_ID` 环境变量
6. **国内数据用 AKShare，国外数据用 yfinance**，不要反过来
7. **模板无硬编码数据**，所有表格行均从 market_data.json 和 ai_texts.json 动态生成

---

## 质量自检 Checklist（核心项）

- [ ] 美股三大指数 + A股指数数据完整
- [ ] 方向判断明确，不含糊其辞
- [ ] 板块方向有逻辑支撑
- [ ] 包含仓位建议和参与节奏
- [ ] 不含残留 `{{}}` 占位符

> 完整 Checklist 详见 `references/style_guide.md`

---

## 选股评分体系

采用 **三层映射法(70分) + 技术面(30分) = 总分100分** 评分体系。

**评级标准**：
- ≥85分 → ⭐⭐⭐⭐⭐ 强烈推荐
- 75-84分 → ⭐⭐⭐⭐ 推荐
- 60-74分 → ⭐⭐⭐ 一般观察
- <60分 → ⭐⭐ 不建议

> 完整评分表详见 `references/style_guide.md` 或 `knowledge-bases/stock-methodology/stock_selection_guide.md`

---

## 市场情绪色彩体系

| 情绪阶段 | CSS类 | 适用场景 |
|----------|-------|----------|
| 高涨（狂热） | `sentiment-hot` | 连续大涨、涨停潮 |
| 温和（乐观） | `sentiment-warm` | 温和上涨、板块轮动 |
| 寒冷（恐慌） | `sentiment-cold` | 下跌调整、缩量 |
| 极寒（冰点） | `sentiment-frozen` | 暴跌、恐慌性抛售 |

`SENTIMENT_CLASS` 由脚本根据市场数据自动推导。

---

## AI 输出字段清单

`ai_texts.json` 需提供 22 个字段（18个AI生成 + 4个脚本推导）。

**关键字段**：MARKET_TONE、US_IMPACT_ON_A、SECTOR_DIRECTIONS、STOCK_SELECTION、SENTIMENT_CLASS 等

> 完整字段清单 + 格式示例详见 `references/style_guide.md`

---

## 异常处理与降级策略

| 异常场景 | 处理方式 |
|----------|----------|
| 美股数据完全无法获取 | 标注"数据缺失"，基于A股自身分析 |
| A股指数部分缺失 | 已有指数正常展示，缺失的显示"—" |
| WebSearch 数据质量差 | 多关键词交叉搜索，中英文验证 |
| 非交易日触发 | 提示今日非交易日，不执行完整流程 |

> 完整异常处理策略详见 `references/style_guide.md`

---

## 版本历史

### v3.3（2026-06-14）
- ✅ 飞书推送功能（`--feishu-push`）
- ✅ 文档优化：新增快速开始、精简冗余部分、详细规范移至 `references/style_guide.md`

### v3.2（2026-06-14）
- ✅ Cloudflare 部署、股票跟踪功能

### v3.0-v3.1（2026-06-14）
- ✅ 核心重构、健壮性优化、选股评分体系

> 完整版本历史见 Git 提交记录

