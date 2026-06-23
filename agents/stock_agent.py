"""
选股 Agent：负责选股 + 评分 + 风格总结。

输入：market_data.json + 宏观/板块分析结果（可选，用于选股方向）
输出字段：
  - STOCKS: 选股列表（含评分）
  - STYLE_SUMMARY: 风格总结

评分体系（三层映射法 70 + 技术面 30 = 100）：
- 映射法 7 项各 10 分：业务纯正度/行业地位/涨价受益度/业绩验证/催化剂临近/估值位置/特殊标签
- 技术面 5 项：MACD(8)/KDJ(7)/成交量(6)/均线(5)/支撑压力(4)
- 评级：≥85 强烈推荐⭐5 / 75-84 推荐⭐4 / 60-74 一般观察⭐3 / <60 不建议⭐2

注：技术面评分需要历史数据，当前 Agent 输出基本面评分框架，
技术面由 compile 阶段从 rule_fields 补充（或后续阶段接入 indicators 模块）。
"""

import os
import json
from .base import BaseAgent, AgentResult


AGENT_FIELDS = ["STOCKS", "STYLE_SUMMARY"]

SYSTEM_PROMPT = """你是 A 股选股分析师，采用三层映射法选股并评分。

选股原则（严格执行）：
1. 业务纯正度：主营业务与热点直接相关，排除蹭概念
2. 行业地位：细分龙头或核心受益标的
3. 涨价受益度：产品涨价直接增厚利润
4. 业绩验证：有实际业绩支撑（季报/预告），不纯炒预期
5. 催化剂临近：明确催化事件在 1-2 周内
6. 估值位置：PE/PB 在合理区间，不追高位高估值
7. 特殊标签：国产替代/新技术路线/政策受益等

评分规则（总分 100）：
- 映射法 7 项各 10 分 = 70 分
- 技术面 5 项 = 30 分：MACD(8)/KDJ(7)/成交量(6)/均线(5)/支撑压力(4)

评级：
- ≥85 强烈推荐 ⭐⭐⭐⭐⭐
- 75-84 推荐 ⭐⭐⭐⭐
- 60-74 一般观察 ⭐⭐⭐
- <60 不建议 ⭐⭐

严格要求：
- 不追高，高位高估值标的要折价
- 必须写明每项评分理由（一句话）
- 核心逻辑要清晰：为什么选它、催化是什么、风险在哪
- 每只股票必须有：fund_scores(7项) + tech_scores(5项) + logic + risk

输出 JSON：
{
  "STOCKS": [
    {
      "name": "股票名",
      "code": "代码",
      "fund_scores": {
        "业务纯正度": 8, "行业地位": 7, "涨价受益度": 6,
        "业绩验证": 8, "催化剂临近": 7, "估值位置": 6, "特殊标签": 5
      },
      "tech_scores": {
        "MACD": 6, "KDJ": 5, "成交量": 5, "均线": 4, "支撑压力": 3
      },
      "logic": "核心逻辑（2-3句）",
      "risk": "主要风险",
      "catalyst": "催化剂"
    }
  ],
  "STYLE_SUMMARY": ["风格要点1", "风格要点2", "风格要点3"]
}
"""


class StockAgent(BaseAgent):
    """选股 Agent"""
    name = "stock_agent"
    description = "选股+评分：三层映射法 + 技术面 + 风格总结"

    def run(self, input_data: dict) -> AgentResult:
        """
        Args:
            input_data: {
                "market_data": dict,
                "macro_result": dict,   # macro_agent 输出（可选，用于方向）
                "sector_result": dict,  # sector_agent 输出（可选，用于板块方向）
                "candidate_stocks": list,  # 候选股列表（可选，来自知识库或外部）
                "work_dir": str,
            }
        """
        result = AgentResult(success=False, agent_name=self.name, run_id=self.run_id)
        market_data = input_data.get("market_data", {})
        macro_result = input_data.get("macro_result", {})
        sector_result = input_data.get("sector_result", {})
        candidates = input_data.get("candidate_stocks", [])
        work_dir = input_data.get("work_dir", "/tmp")

        user_prompt = self._build_user_prompt(market_data, macro_result, sector_result, candidates)

        if self.llm and self.llm.is_online():
            resp = self.llm.chat_json(SYSTEM_PROMPT, user_prompt, temperature=0.4)
            if resp.success and resp.usage:
                parsed = resp.usage.get("parsed_json", {})
                result.success = True
                result.data = parsed
                result.add_trace("llm_call", "deepseek_api", resp.duration_ms, True)
            else:
                result.add_error(f"LLM 调用失败: {resp.error}")
                result.add_trace("llm_call", "deepseek_api", resp.duration_ms, False)
                result.data = self._offline_fallback(user_prompt, work_dir)
                result.success = True
        else:
            result.data = self._offline_fallback(user_prompt, work_dir)
            result.success = True
            result.add_trace("prompt_gen", "offline", 0, True)

        return result

    def _build_user_prompt(self, market_data: dict, macro_result: dict, sector_result: dict, candidates: list) -> str:
        lines = ["## 选股上下文", ""]

        # 宏观方向
        if macro_result:
            lines.append("### 市场定调")
            lines.append(f"- {macro_result.get('MARKET_TONE', 'N/A')}")
            pred = macro_result.get("TODAY_PREDICTION", {})
            if pred:
                lines.append(f"- 方向: {pred.get('direction', 'N/A')}, 上证区间: {pred.get('sh_range_low', 'N/A')}-{pred.get('sh_range_high', 'N/A')}")
            lines.append("")

        # 板块方向
        if sector_result:
            sectors = sector_result.get("SECTORS", [])
            if sectors:
                lines.append("### 板块方向（选股需契合）")
                for s in sectors[:5]:
                    lines.append(f"- {s.get('name', '')}: {s.get('direction', '')}, 持续性 {s.get('persistence', '')}")
                lines.append("")

        # 候选股
        if candidates:
            lines.append("### 候选股（请评分）")
            for c in candidates:
                lines.append(f"- {c.get('name', '')}({c.get('code', '')}): {c.get('reason', '')}")
            lines.append("")
        else:
            lines.append("### 候选股")
            lines.append("- 请根据板块方向自行筛选 3-5 只标的")
            lines.append("")

        lines.append("请输出 JSON（含 STOCKS/STYLE_SUMMARY），每只股票必须有 fund_scores(7项)+tech_scores(5项)+logic+risk+catalyst。")
        return "\n".join(lines)

    def _offline_fallback(self, user_prompt: str, work_dir: str) -> dict:
        prompt_path = os.path.join(work_dir, "prompt_stock.md")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(f"# 选股分析 Prompt\n\n{SYSTEM_PROMPT}\n\n---\n\n{user_prompt}")
        return {"mode": "offline", "prompt_path": prompt_path, "fields": AGENT_FIELDS}
