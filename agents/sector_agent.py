"""
板块分析 Agent：负责板块方向 + 资金流向 + 昨日复盘 + 信号监控。

输入：market_data.json（yesterday.sectors / main_fund_flow / north_bound）
输出字段：
  - SECTORS: 板块方向分析（领涨/领跌 + 持续性判断）
  - YESTERDAY_REVIEW: 昨日盘面复盘
  - SIGNALS: 信号监控（多空信号 + 强度）
"""

import os
import json
from .base import BaseAgent, AgentResult


AGENT_FIELDS = ["SECTORS", "YESTERDAY_REVIEW", "SIGNALS"]

SYSTEM_PROMPT = """你是 A 股板块分析师，负责：
1. 分析昨日领涨/领跌板块的方向与持续性
2. 复盘昨日盘面特征（资金流向/北向/成交结构）
3. 识别多空信号并评估强度

严格要求：
- 板块持续性判断要看：催化多元性/业绩可见度/资金持续性
- 信号监控要区分：趋势信号/资金信号/情绪信号/技术信号
- 不追高，对拥挤赛道要提示风险
- 数据基于提供的 market_data.json

输出 JSON：
{
  "SECTORS": [
    {"name": "板块名", "direction": "偏多|震荡|偏空", "persistence": "高|中|低", "reasoning": "逻辑"},
  ],
  "YESTERDAY_REVIEW": "昨日盘面复盘（3-5句）",
  "SIGNALS": [
    {"type": "趋势|资金|情绪|技术", "name": "信号名", "status": "当前状态", "strength": "强|中|弱"},
  ]
}
"""


class SectorAgent(BaseAgent):
    """板块分析 Agent"""
    name = "sector_agent"
    description = "板块分析：领涨领跌 + 资金流向 + 昨日复盘 + 信号监控"

    def run(self, input_data: dict) -> AgentResult:
        result = AgentResult(success=False, agent_name=self.name, run_id=self.run_id)
        market_data = input_data.get("market_data", {})
        work_dir = input_data.get("work_dir", "/tmp")

        user_prompt = self._build_user_prompt(market_data)

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

    def _build_user_prompt(self, market_data: dict) -> str:
        yesterday = market_data.get("yesterday", {})
        sectors = yesterday.get("sectors", {}) or {}
        fund_flow = yesterday.get("main_fund_flow", {})
        north_bound = yesterday.get("north_bound", {})
        turnover = yesterday.get("turnover", {})

        lines = ["## 板块与资金数据", ""]

        # 板块
        top_gainers = sectors.get("top_gainers", []) if isinstance(sectors, dict) else []
        top_losers = sectors.get("top_losers", []) if isinstance(sectors, dict) else []
        if top_gainers:
            lines.append("### 领涨板块")
            for s in top_gainers[:8]:
                lines.append(f"- {s.get('name', '')}: 涨幅 {s.get('pct_change', 'N/A')}%, 净流入 {s.get('net_inflow', 'N/A')}亿")
            lines.append("")
        if top_losers:
            lines.append("### 领跌板块")
            for s in top_losers[:8]:
                lines.append(f"- {s.get('name', '')}: 跌幅 {s.get('pct_change', 'N/A')}%, 净流出 {s.get('net_inflow', 'N/A')}亿")
            lines.append("")

        # 主力资金
        if fund_flow:
            lines.append("### 主力资金")
            lines.append(f"- 净流入: {fund_flow.get('net_inflow', 'N/A')}亿")
            lines.append("")

        # 北向
        if north_bound:
            lines.append("### 北向资金")
            lines.append(f"- 净额: {north_bound.get('net_inflow', 'N/A')}（注：2024-08-19 后官方停披露净买入额）")
            lines.append("")

        if turnover:
            lines.append(f"### 成交额: {turnover.get('total', 'N/A')}亿")
            lines.append("")

        lines.append("请输出 JSON（含 SECTORS/YESTERDAY_REVIEW/SIGNALS）。")
        return "\n".join(lines)

    def _offline_fallback(self, user_prompt: str, work_dir: str) -> dict:
        prompt_path = os.path.join(work_dir, "prompt_sector.md")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(f"# 板块分析 Prompt\n\n{SYSTEM_PROMPT}\n\n---\n\n{user_prompt}")
        return {"mode": "offline", "prompt_path": prompt_path, "fields": AGENT_FIELDS}
