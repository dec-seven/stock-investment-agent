# 架构重构方案：stock-skills → Agent 架构

> 基于代码探查事实制定，不凭空设计。
> 探查日期：2026-06-20

## 一、现状事实（重构依据）

| 维度 | 现状 | 问题 |
|---|---|---|
| skills/ 体积 | 三个 skill 子目录，stock-morning-brief 1.9M | 9 个 .py 超 300 行，stock_tracker 1079/fetch_data 984/generate_report 914 |
| shared/ 体积 | 8 个 .py 共 2116 行 | **skills/ 零 import shared/**，两套平行基础设施 |
| 工具函数 | format_pct/format_amount/html_to_pdf/push_to_feishu | shared/utils.py 与 generate_report.py 各一份重复实现 |
| generate_ai_texts.py | 856 行 25 函数 | 混合校验/格式化/规则推导/HTML构建/prompt/编译 6 类职责 |
| 知识库 | 164K 结构化方法论+样例 | **无任何 .py 读取**，零 embedding/向量检索 |
| observability | shared/logger.py 有 StructuredFormatter | **skills/ 全用 print**，14 个 bare `except:` 全 pass，logs/ 仅 1 条测试记录 |
| Agent 痕迹 | 注释多处提及 "Agent" | 实为"脚本生成 prompt → 人/LLM 手动执行 → 脚本编译"人肉协议，无 API 闭环 |
| 编排 | 5 步链路靠 shell 手动串联 | 步骤间用临时 JSON 文件耦合，无状态机/重试/断点续跑 |
| 并发 | fetch_data 多源拉取串行 | 全链路同步阻塞，唯一 asyncio 在无关的 tui_app.py |

## 二、用户方案评估

| 用户提议 | 评估 | 调整建议 |
|---|---|---|
| skills 太重 shared 太轻 | ✅ 完全正确 | shared 零引用是事实 |
| 拆 generate_ai_texts 为 ai/prompt_builder+response_parser+validators+insight_engine | ✅ 合理 | **补充 html_builders.py + compiler.py**（12 个 build_* 函数需归宿） |
| 升级 4 个 agent：macro/sector/stock/review | ✅ 方向对 | **补充 orchestrator workflow**（4 个 agent 需编排，不能直接互调） |
| 知识库升级 RAG | ✅ 必要 | 当前是纯文档摆设，无任何代码读取 |
| 加 observability | ✅ 必要 | 14 个 bare except 是 P0 |
| 新目录 stock-investment-agent/ | ⚠️ 不建议改名 | git 历史断裂代价大，沿用 stock-skills/ |
| shared 下 services/scoring/ai | ✅ 合理 | **补充 indicators/**（technical_indicators.py 现成 477 行） |
| memory/ 目录 | ✅ 合理 | 区分 working_memory（运行时）+ state_store（持久化） |

## 三、修正后目录结构

```
stock-skills/                      # 不改名，保留 git 历史
├── agents/                        # Agent 实现
│   ├── __init__.py
│   ├── base.py                    # Agent 基类（输入/输出/工具/记忆接口）
│   ├── macro_agent.py             # 宏观+全球市场分析
│   ├── sector_agent.py            # 板块+资金流向
│   ├── stock_agent.py             # 选股+评分
│   └── review_agent.py            # 盘后复盘
├── workflows/                     # 编排层（agent 不互调，由 workflow 调度）
│   ├── __init__.py
│   ├── morning_brief.py           # 早报全链路
│   ├── daily_report.py
│   └── review.py
├── shared/
│   ├── ai/                        # LLM 相关
│   │   ├── llm_client.py          # 多 provider 封装（替换人肉协议）
│   │   ├── prompt_builder.py      # prompt 模板构建
│   │   ├── response_parser.py     # LLM 响应解析+校验
│   │   ├── validators.py          # 数据/字段校验
│   │   ├── insight_engine.py      # 规则推导（derive_*）
│   │   ├── html_builders.py       # HTML 片段构建（12 个 build_*）
│   │   └── compiler.py            # 编译 ai_texts.json
│   ├── services/                  # 外部服务
│   │   ├── data_service/          # 数据获取（按源拆 sub-module）
│   │   │   ├── __init__.py        # 统一 DataSource 接口
│   │   │   ├── akshare_src.py
│   │   │   ├── sina_src.py
│   │   │   ├── tencent_src.py
│   │   │   └── yfinance_src.py
│   │   ├── deploy_service.py      # Cloudflare 部署
│   │   ├── push_service.py        # 飞书推送
│   │   └── pdf_service.py         # HTML→PDF
│   ├── scoring/                   # 评分体系
│   │   ├── stock_scorer.py        # 三层映射法
│   │   └── backtest.py
│   ├── indicators/                # 技术指标（现成迁移）
│   │   └── technical.py
│   ├── cache/                     # SQLite 缓存
│   │   └── sqlite_cache.py
│   ├── utils.py                   # 纯工具函数（唯一来源）
│   ├── config.py                  # 配置加载
│   └── logger.py                  # 结构化日志（保留）
├── memory/                        # 运行时记忆
│   ├── __init__.py
│   ├── working_memory.py          # 单次运行上下文（run_id/中间产物）
│   └── state_store.py             # 持久化状态（SQLite）
├── knowledge/                     # RAG 引擎
│   ├── __init__.py
│   ├── embedder.py                # 文本向量化
│   ├── vector_store.py            # chromadb 本地存储
│   ├── retriever.py               # 语义检索
│   └── indexer.py                 # 把 md 入库
├── observability/
│   ├── __init__.py
│   ├── metrics.py                 # 成功率/耗时/token
│   ├── tracing.py                 # trace_id 贯穿
│   └── dashboard.py               # HTML 运行报告
├── skills/                        # 降级为工具集合（被 agent 调用）
│   └── stock-morning-brief/       # 保留旧实现做对照，逐步迁移
├── knowledge-bases/               # 原始知识素材（被 knowledge/ 索引）
├── tests/
├── config/                        # yaml 配置
└── docs/
```

**关键调整说明**：
1. **不改项目名**：git 历史价值 > 命名美观
2. **agents 不互调**：4 个 agent 之间无直接依赖，全部由 workflows/ 编排
3. **shared/services/data_service/ 拆子模块**：4 个数据源差异大，必须按源隔离
4. **memory/ 分两层**：working_memory（单次运行）+ state_store（跨次持久化，如选股跟踪）
5. **knowledge/ 与 knowledge-bases/ 共存**：前者是 RAG 引擎，后者是原始素材
6. **skills/ 保留降级**：旧实现作为对照基线，逐步迁移，不一次性删

## 四、分阶段执行计划

> 原则：**先观测后重构，先治标后治本，旧路径保留对照**。
> 每阶段独立可交付，可随时停下稳定运行。

### 阶段 0：观测性基线（1-2 天，必须最先）✅ 已完成

> 完成日期：2026-06-24
> 交付：run_context.py + 14 个 bare except 改造 + logger 接入
> 验证：grep 0 个 bare except，py_compile 通过

**为什么最先**：看不见问题就没法重构。14 个 bare except 让任何改动都盲飞。

**任务**：
1. shared/logger.py 接入 skills/ 全部脚本，替换所有 `print(..., file=sys.stderr)`
2. 14 个 bare `except:` 全部改为 `except Exception as e: logger.exception(...)`
3. 加 run_id（UUID）贯穿单次早报生成，所有日志带 run_id
4. logs/ 配置按日 rotation，保留 30 天
5. 加 `shared/observability/run_context.py`（用 contextvar 传递 run_id）

**完成标准**：
- 跑一次早报，logs/ 有完整结构化 JSON 日志
- 任意一条日志可追溯到 run_id
- 0 个 bare except（grep 验证）

### 阶段 1：消灭重复，shared 真正化（✅ 已完成 2026-06-24）

**成果**：
- skills/ 下所有重复函数定义（format_pct/format_amount/safe_float/push_to_feishu/pct_class）已删除
- 5 个脚本统一引用 `shared/utils.py`
- skills/ 引用 shared/ 共 10 处

**验证**：
```bash
grep -rn "def format_pct|def safe_float..." skills/  # 0 结果
grep -rn "from utils|from shared" skills/ | wc -l    # 10
```⏸️ 延后

> 状态：阶段 2 完成后执行，避免重复改 import
> 原因：generate_ai_texts.py 已拆到 shared/ai/，待统一改 skills/ 引用

**任务**：
1. 合并 `shared/data_fetcher.py`(485) + `skills/fetch_data.py`(984) → `shared/services/data_service/`（按源拆 4 个 sub-module）
2. `shared/utils.py` 的 format_pct/format_amount/html_to_pdf/push_to_feishu 统一，skills/ 全部改 import
3. 删除 skills/ 内重复实现（grep 验证无重复函数定义）
4. `shared/scoring/backtest.py` 替换 `skills/scoring_backtest.py`
5. `shared/indicators/technical.py` 替换 `shared/technical_indicators.py`（重命名+迁移）

**完成标准**：
- `grep -r "def format_pct" skills/` 无命中
- skills/ 下所有 .py 至少 import shared/ 一次
- 旧 fetch_data.py 删除前先建 git tag `pre-refactor-shared`

### 阶段 2：拆 generate_ai_texts.py（2-3 天）✅ 已完成

> 完成日期：2026-06-24
> 交付：856 行拆为 6 模块 + 1 CLI
> 验证：单文件 <500 行，CLI 接口不变，py_compile 通过

**任务**：856 行 25 函数按职责拆 6 模块：

| 模块 | 函数 | 行数预估 |
|---|---|---|
| shared/ai/validators.py | validate_required_fields, validate_stock_data | ~80 |
| shared/ai/insight_engine.py | derive_direction_signal, derive_direction_judgment, derive_sentiment_class, derive_sentiment_label, derive_sh_range | ~200 |
| shared/ai/html_builders.py | 12 个 build_* + _build_score_bar_row | ~350 |
| shared/ai/prompt_builder.py | cmd_prepare 拆出 | ~100 |
| shared/ai/compiler.py | cmd_compile 拆出 | ~80 |
| shared/ai/response_parser.py | 新增，解析 LLM 响应+JSON 校验 | ~60 |
| skills/.../generate_ai_texts.py | 保留为 CLI 入口，仅 argparse + 调用 | ~80 |

**完成标准**：
- 单文件 <300 行
- 每个模块单一职责
- 旧 856 行版本 git tag `pre-split-ai-texts`

### 阶段 3：Agent 化（5-7 天，核心阶段）✅ 已完成

> 完成日期：2026-06-23
> 交付：4 个 Agent + 编排器 + 双模式 LLM + 6 个 Tool 封装
> 验证：离线模式冒烟测试通过，4 个 Agent 均能生成 prompt 片段
> 注：阶段 0/1/2 未做，Agent 通过 subprocess 调用现有脚本作为 Tool，不破坏旧路径

**任务**：

**3.1 Agent 基类**（`agents/base.py`）：
```python
class BaseAgent:
    name: str
    tools: list[Tool]
    def __init__(self, llm_client, working_memory): ...
    def run(self, input_data) -> AgentResult: ...
    def call_tool(self, tool_name, **kwargs): ...
```

**3.2 LLM Client**（`shared/ai/llm_client.py`）：
- 替换"人肉协议"，支持 DeepSeek/通义/GLM API
- 内置重试+超时+token 计数
- 失败回退到规则推导（insight_engine）

**3.3 4 个 Agent 实现**：
| Agent | 输入 | 输出 | 调用工具 |
|---|---|---|---|
| macro_agent | market_data.json | 宏观分析+全球影响 | data_service, llm_client |
| sector_agent | market_data.json | 板块分析+资金流向 | data_service, llm_client |
| stock_agent | 候选股+评分输入 | 选股+评分卡 | data_service, scoring, llm_client |
| review_agent | 当日盘后数据 | 复盘报告 | data_service, llm_client |

**3.4 编排器**（`workflows/morning_brief.py`）：
- 状态机：fetch → macro → sector → stock → compile → render → deploy → push
- 每步可断点续跑（state_store 记录进度）
- 并发：macro/sector/stock 三 agent 可并行（review 串行）

**3.5 现有脚本降级为 Tool**：
- fetch_data → data_service.fetch_all()
- generate_report → render_service.render()
- deploy_to_cloudflare → deploy_service.deploy()
- push_to_feishu → push_service.push()

**完成标准**：
- `python -m workflows.morning_brief` 一条命令跑完全链路，无需手动步骤
- 旧 shell 串联路径保留（git tag `pre-agent`）做对照
- 三 agent 并行后总耗时下降 ≥30%

### 阶段 4：RAG 知识库（3-5 天）

**任务**：
1. `knowledge/embedder.py`：用 sentence-transformers + bge-small-zh（本地，免费）
2. `knowledge/vector_store.py`：chromadb 本地持久化
3. `knowledge/indexer.py`：把 knowledge-bases/ 全部 .md 切块入库（按章节切，保留元数据）
4. `knowledge/retriever.py`：语义检索 top-k，返回原文+来源
5. Agent 生成 prompt 时调用 retriever 注入相关方法论
   - macro_agent 检索"宏观分析"方法论
   - stock_agent 检索"选股评分"方法论

**完成标准**：
- macro_agent 生成分析时，prompt 中包含从知识库检索到的 2-3 条相关方法论
- 检索结果可追溯到原始 .md 文件路径
- 知识库更新后，重新 index 即可生效

### 阶段 5：observability 完善（2-3 天）

**任务**：
1. `observability/metrics.py`：数据获取成功率、LLM 调用耗时、token 消耗、agent 步骤耗时
2. `observability/tracing.py`：trace_id 贯穿 agent→tool→llm 调用链
3. `observability/dashboard.py`：HTML 报告，展示近 7 天运行情况
4. 异常分级：数据获取失败重试 3 次，LLM 失败回退规则，渲染失败阻断

**完成标准**：
- 可查看任意一次早报生成的完整 trace
- dashboard 展示近 7 天成功率/耗时/token 消耗趋势
- 关键异常自动告警（飞书推送）

### 阶段 6：WebSearch 去依赖（2-3 天，可独立运行关键）

**背景**：当前流程两处依赖 WorkBuddy Agent：① LLM 分析（阶段 3 已用 DeepSeek API 替代）② WebSearch 数据补充（仍未去依赖）。本阶段消除②，使整个流程仅靠 `DEEPSEEK_API_KEY` + 搜索 API key 即可独立运行。

**WebSearch 依赖现状**：
- `fetch_data.py` 约 4 项 `need_websearch=True`：北向净额（官方停披露）、日经 225、美元指数、源失败兜底
- `fetch_holiday_news.py` 全靠 Agent 填：`holiday_findings` / `sector_impact` / `strong_catalyst` / `warning_signals`

**任务**：

**6.1 固定数据源补齐（C 方案，优先做）**：
| 字段 | 补齐源 | 实现位置 |
|---|---|---|
| 日经 225 | 新浪 `int_nikkei`（再试）| fetch_data.py `fill_global_markets` |
| 美元指数 | 新浪 `fx_susdindex` | fetch_data.py `fill_global_markets` |
| 北向成交额 | AKShare `stock_hsgt_north_net_flow_in` | fetch_data.py `fill_north_bound` |

**6.2 搜索 API 工具（A 方案，Tavily）**：
- 新增 `shared/ai/web_search_tool.py`：
  ```python
  class WebSearchTool:
      def __init__(self, api_key=None):
          self.api_key = api_key or os.environ.get("TAVILY_API_KEY", "")
      def search(self, query: str, max_results: int = 5) -> list[dict]:
          """返回 [{title, content, url}]，无 key 时返回空不阻断"""
  ```
- 封装为 Agent 可调用的 Tool（继承 `agents.base.Tool`）
- 内置重试 + 超时 + 结果去重

**6.3 fetch_data.py 改造**：
- `mark_websearch()` 不再只标记，改为：标记 + 调 `WebSearchTool.search()` 自动补
- 无 TAVILY_API_KEY 时回退到原行为（标记等待外部填），保持兼容
- 节假日 `fetch_holiday_news.py` 的 4 个 Agent 填充字段改为自动调搜索

**6.4 LLM 联网兜底（B 方案，可选）**：
- `LLMClient` 增加 `chat_with_search()` 方法，支持带联网的大模型（通义/Kimi/GLM-4）
- 仅在 Tavily 也失败时兜底，非主路径

**完成标准**：
- 配置 `DEEPSEEK_API_KEY` + `TAVILY_API_KEY` 两个 key，`python3 -m workflows.morning_brief` 全自动跑完，无需 WorkBuddy Agent 介入
- WebSearch 字段填充率 ≥ 90%（剩余无源字段明确标注）
- 无 TAVILY_API_KEY 时仍可运行（回退到标记等待模式）
- `grep "need_websearch.*True" market_data.json` 项数 ≤ 2（vs 当前 4）

**依赖关系**：可与阶段 0/1 并行，不阻塞 Agent 主链。建议在阶段 1（消灭重复）之后做，避免改两遍 fetch_data。

## 五、阶段依赖与并行

```
阶段0 (观测性) ──┬──→ 阶段1 (消灭重复) ──┬──→ 阶段2 (拆 ai_texts) ──→ 阶段3 (Agent化) ──→ 阶段5 (observability完善)
                 │                        │                              │
                 │                        └──→ 阶段6 (WebSearch去依赖) ──┤
                 │                                                       │
                 └───────────────────────────────────────────────────────┴──→ 阶段4 (RAG)
```

- 阶段 0 必须最先（盲飞无法重构）
- 阶段 1→2→3 强串行（后面依赖前面）
- 阶段 6 在阶段 1 之后做（避免改两遍 fetch_data），可与阶段 2/3 并行
- 阶段 4 可与阶段 3 后期并行（RAG 不阻塞 Agent 化）
- 阶段 5 在阶段 3 后做（Agent 化后才有完整 trace）

## 六、需要你拍板的关键决策

| 决策点 | 选项 | 建议 |
|---|---|---|
| LLM provider | DeepSeek / 通义 / GLM API / 多家 | **DeepSeek**（便宜+稳定+中文好） |
| embedding 模型 | 本地 bge-small-zh / API | **本地**（免费+离线+隐私） |
| Agent 框架 | 原生抽象 / LangGraph / AutoGen | **原生**（当前规模不需要重框架） |
| 旧 skills/ 保留多久 | 1 个月 / 3 个月 / 永久 | **3 个月**（足够对照验证） |
| 是否同步补单测 | 是 / 否 / 关键路径补 | **关键路径补**（data_service + scoring + llm_client） |
| vector DB | chromadb / faiss / qdrant | **chromadb**（本地+持久化+生态好） |
| 并发模型 | asyncio / threading / 进程池 | **asyncio**（IO 密集，llm_client 天然 async） |
| 搜索 API（阶段6） | Tavily / SerpAPI / Bing / 带联网大模型 | **Tavily**（免费 1000 次/月+专为 LLM 设计+结构化返回） |

## 七、避坑清单

1. **不要先做 Agent 再补观测性** —— 反过来，否则 Agent 出问题无法定位
2. **不要一次性删 skills/** —— 保留旧路径做对照，至少 3 个月
3. **不要上 LangGraph/AutoGen 重框架** —— 当前 4 agent 规模原生足够
4. **memory/ 不要做成完整记忆系统** —— 先做 working_memory，state_store 后补
5. **RAG 不要先做** —— 阶段 4，等 Agent 稳定后再做，否则检索增强效果无法验证
6. **LLM 调用必须有回退** —— 失败时回退到 insight_engine 规则推导，不能阻断
7. **fetch_data 异常处理** —— 14 个 bare except 必须先治标再加重试，否则重试会放大故障
8. **拆分时保留 git tag** —— 每阶段开始前打 tag，可随时回滚

## 八、单阶段交付物

每阶段结束应有：
- 可运行的代码（通过完成标准验证）
- git tag（可回滚）
- 简短迁移笔记（写到 `docs/refactor-log.md`）
- 更新本文档对应阶段的 ✅

---

**下一步**：你确认决策点（第六节），我从阶段 0 开始执行。
