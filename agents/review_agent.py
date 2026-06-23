"""
复盘 Agent：负责风险提示 + 操作策略 + 纪律 + 仓位 + 心态管理。

输入：market_data.json + macro/sector/stock 分析结果
输出字段：
  - RISKS: 风险提示
  - STRATEGY: 操作策略
  - DISCIPLINES: 操作纪律（4条）
  - POSITION_ADVICE: 仓位建议
  - PARTICIPATION_PACE: 参与节奏
  - MENTALITY_ADVICE: 心态管理（含情绪色彩）

注：当前早报流程中，这些字段由 LLM 生成。
后续可拆分为独立 review_agent，用于盘后复盘场景。
"""

import os
import json
from .base import BaseAgent, AgentResult


AGENT_FIELDS = ["RISKS", "STRATEGY", "DISCIPLINES", "POSITION_ADVICE", "PARTICIPATION_PACE", "MENTALITY_ADVICE"]

SYSTEM_PROMPT = """你是 A 股风险控制与策略分析师，负责：
1. 识别市场风险并分级提示
2. 给出操作策略（基于市场定调）
3. 制定操作纪律（4 条，可执行）
4. 仓位建议（0-10 成）
5. 参与节奏（左侧/右侧/观望）
6. 心态管理（基于情绪特征）

严格要求：
- 风险要具体：高位股回调/板块轮动加速/外部冲击/流动性收紧
- 仓位要与方向匹配：偏多 6-8 成，震荡 3-5 成，偏空 1-3 成，防守 0-2 成
- 纪律要可执行：止损位/止盈位/不加仓条件
- 心态管理要匹配情绪色彩（sentiment-hot/warm/cold/frozen）

输出 JSON：
{
  "RISKS": ["风险1", "风险2", "风险3"],
  "STRATEGY": ["策略1", "策略2"],
  "DISCIPLINES": ["纪律1", "纪律2", "纪律3", "纪律4"],
  "POSITION_ADVICE": "仓位建议（含成数）",
  "PARTICIPATION_PACE": "参与节奏",
  "MENTALITY_ADVICE": "心态管理建议"
}
"""


class ReviewAgent(BaseAgent):
    """复盘/策略 Agent"""
    name = "review_agent"
    description = "风险+策略+纪律+仓位+心态管理"

    def run(self, input_data: dict) -> AgentResult:
        result = AgentResult(success=False, agent_name=self.name, run_id=self.run_id)
        market_data = input_data.get("market_data", {})
        macro_result = input_data.get("macro_result", {})
        sector_result = input_data.get("sector_result", {})
        stock_result = input_data.get("stock_result", {})
        work_dir = input_data.get("work_dir", "/tmp")

        user_prompt = self._build_user_prompt(market_data, macro_result, sector_result, stock_result)

        if self.llm and self.llm.is_online():
            resp = self.llm.chat_json(SYSTEM_PROMPT, user_prompt, temperature=0.3)
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

    def _build_user_prompt(self, market_data: dict, macro_result: dict, sector_result: dict, stock_result: dict) -> str:
        lines = ["## 策略分析上下文", ""]

        if macro_result:
            lines.append("### 市场定调")
            lines.append(f"- {macro_result.get('MARKET_TONE', 'N/A')}")
            pred = macro_result.get("TODAY_PREDICTION", {})
            if pred:
                lines.append(f"- 方向: {pred.get('direction', 'N/A')}, 情绪: {macro_result.get('EMOTION_FEATURE', 'N/A')}")
            lines.append("")

        if sector_result:
            sectors = sector_result.get("SECTORS", [])
            if sectors:
                lines.append("### 板块方向")
                for s in sectors[:5]:
                    lines.append(f"- {s.get('name', '')}: {s.get('direction', '')}")
                lines.append("")

        if stock_result:
            stocks = stock_result.get("STOCKS", [])
            if stocks:
                lines.append("### 选股（需对应策略）")
                for s in stocks:
                    lines.append(f"- {s.get('name', '')}: 核心逻辑 {s.get('logic', '')[:30]}")
                lines.append("")

        lines.append("请输出 JSON（含 RISKS/STRATEGY/DISCIPLINES/POSITION_ADVICE/PARTICIPATION_PACE/MENTALITY_ADVICE）。")
        return "\n".join(lines)

    def _offline_fallback(self, user_prompt: str, work_dir: str) -> dict:
        prompt_path = os.path.join(work_dir, "prompt_review.md")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(f"# 策略分析 Prompt\n\n{SYSTEM_PROMPT}\n\n---\n\n{user_prompt}")
        return {"mode": "offline", "prompt_path": prompt_path, "fields": AGENT_FIELDS}
