# Legacy Scripts 遗留脚本

> 本目录存放已被新架构替代的旧脚本，保留作为历史对照。
> 创建日期：2026-06-24

## ⚠️ 重要说明

**这些脚本已不再使用**，新架构通过 `agents/` + `workflows/` + `shared/` 实现。

保留目的：
1. 历史对照（3 个月后可删除）
2. 回溯问题时的参考
3. 迁移验证

---

## 📄 脚本列表与替代方案

| 脚本 | 原用途 | 新架构替代 |
|------|--------|-----------|
| `stock_tracker.py` | 维护入选股票跟踪 | `agents/learning_agent.py` + `memory/state_store.py` |
| `validate_llm_json.py` | 验证 LLM 输出 JSON 格式 | `shared/ai/validators.py` + `shared/ai/response_parser.py` |
| `validate_market_data.py` | 验证市场数据完整性 | `shared/ai/validators.py` |
| `fetch_closing_data.py` | 获取收盘数据 | `shared/services/data_service/`（待实现） |
| `fetch_holiday_news.py` | 获取节假日新闻 | `shared/services/data_service/`（待实现） |
| `generate_review.py` | 生成复盘报告 | `workflows/review.py`（待实现） |
| `save_prediction_snapshot.py` | 保存预测快照 | `memory/state_store.py`（待实现） |

---

## 🔄 迁移时间表

根据 `REFACTOR_PLAN.md` 分阶段执行：

| 阶段 | 内容 | 状态 |
|------|------|------|
| 阶段 0 | 观测性基线 | ✅ 已完成 |
| 阶段 1 | 消灭重复，shared 真正化 | ✅ 已完成 |
| 阶段 2 | 拆 generate_ai_texts.py | ✅ 已完成 |
| 阶段 3 | Agent 化 | ✅ 已完成 |
| 阶段 4 | RAG 知识库 | 🚧 规划中 |
| 阶段 5 | observability 完善 | 🚧 规划中 |
| 阶段 6 | WebSearch 去依赖 | 🚧 规划中 |

---

## 🗑️ 删除计划

根据 `REFACTOR_PLAN.md` 建议：

> **保留 3 个月作为对照**，之后可删除。

预计删除时间：**2026-09-24**

---

## 📞 联系

如有疑问，查看：
- 架构方案：`REFACTOR_PLAN.md`
- 新架构代码：`agents/` / `workflows/` / `shared/`
- 项目记忆：`.workbuddy/memory/MEMORY.md`
