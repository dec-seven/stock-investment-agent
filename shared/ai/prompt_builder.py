#!/usr/bin/env python3
"""
LLM 分析提示词构建模块

从 market_data.json 构建 LLM 分析所需的提示词,包含数据摘要和规则推导结果。
提取 cmd_prepare() 函数中的提示词构建逻辑。

函数列表:
- build_data_summary(): 将 market_data.json 压缩成 LLM 友好的文本摘要
- build_analysis_prompt(): 生成完整的 LLM 分析提示词
"""

import os
import sys
from datetime import datetime
from typing import Dict

# 导入日志和工具
sys.path.insert(0, str(__file__).replace('/shared/ai/prompt_builder.py', ''))
from shared.logger import get_logger
from shared.ai.insight_engine import (
    derive_direction_signal,
    derive_direction_judgment,
    derive_sentiment_class,
    derive_sh_range
)

logger = get_logger('prompt_builder')


def format_pct(val: float) -> str:
    """格式化涨跌幅"""
    if val is None:
        return "—"
    if val > 0:
        return f"+{val:.2f}%"
    if val < 0:
        return f"{val:.2f}%"
    return "0.00%"


def format_amount(val: float) -> str:
    """格式化金额(亿)"""
    if val is None:
        return "—"
    if abs(val) >= 10000:
        return f"{val/10000:.2f}万亿"
    return f"{val:.0f}亿"


def build_data_summary(data: Dict) -> str:
    """
    将 market_data.json 压缩成 LLM 友好的文本摘要
    
    提取关键数据:指数行情、市场广度、成交额、北向资金、板块、隔夜美股、全球市场、新闻事件。
    
    Args:
        data: market_data.json 的完整数据字典
    
    Returns:
        str: Markdown 格式的数据摘要文本
    
    Example:
        >>> summary = build_data_summary(data)
        >>> print(summary)
        ## A股昨日行情
        - 上证指数: 4,050.00 (+1.25%)
        - 市场广度: 上涨/下跌: 3000 / 1500
        ...
    """
    lines = []
    yesterday = data.get("yesterday", {})
    us = data.get("overnight_us", {})
    global_m = data.get("global_markets", {})
    news = data.get("news_events", {})
    
    # A股指数
    lines.append("## A股昨日行情")
    for idx in yesterday.get("indices", []):
        if not idx.get("need_websearch"):
            lines.append(f"- {idx['name']}: {idx['close']:,.2f} ({format_pct(idx['pct'])})")
    
    # 市场广度
    breadth = yesterday.get("market_breadth", {})
    if breadth and not breadth.get("need_websearch"):
        lines.append(f"\n## 市场广度")
        lines.append(f"- 上涨/下跌: {breadth.get('up_count', 0)} / {breadth.get('down_count', 0)}")
        lines.append(f"- 涨停/跌停: {breadth.get('limit_up', 0)} / {breadth.get('limit_down', 0)}")
    
    # 成交额
    turnover = yesterday.get("turnover", {})
    if turnover and turnover.get("total", 0) > 0:
        lines.append(f"- 两市成交: {format_amount(turnover['total'])}")
    
    # 北向资金
    north = yesterday.get("north_bound", {})
    if north and north.get("net_inflow") is not None:
        nf = north["net_inflow"]
        sign = "+" if nf > 0 else ""
        lines.append(f"- 北向资金: 净流入 {sign}{nf:.0f}亿")
    
    # 板块
    sectors = yesterday.get("sectors", {})
    gainers = sectors.get("top_gainers", [])
    losers = sectors.get("top_losers", [])
    if gainers:
        lines.append(f"\n## 领涨板块")
        for s in gainers[:3]:
            if not s.get("need_websearch"):
                lines.append(f"- {s['name']} ({format_pct(s['pct'])})")
    if losers:
        lines.append(f"\n## 领跌板块")
        for s in losers[:3]:
            if not s.get("need_websearch"):
                lines.append(f"- {s['name']} ({format_pct(s['pct'])})")
    
    # 隔夜美股
    lines.append(f"\n## 隔夜美股")
    for key in ["dow", "sp500", "nasdaq", "vix", "sox", "nvda", "tsla", "oil", "gold"]:
        item = us.get(key, {})
        if item and not item.get("need_websearch"):
            name = item.get("name", key)
            close = item.get("close")
            pct = item.get("pct")
            reason = item.get("reason", "")
            close_str = f"{close:,.2f}" if close is not None else "—"
            line = f"- {name}: {close_str} ({format_pct(pct)})"
            if reason:
                line += f" — {reason}"
            lines.append(line)
    
    # 全球市场
    lines.append(f"\n## 全球市场")
    for key in ["nikkei", "hsi", "dxy", "cnh"]:
        item = global_m.get(key, {})
        if item and not item.get("need_websearch"):
            name = item.get("name", key)
            close = item.get("close")
            pct = item.get("pct")
            close_str = f"{close:,.2f}" if close is not None else "—"
            lines.append(f"- {name}: {close_str} ({format_pct(pct)})")
    
    # 新闻事件
    items = news.get("items", [])
    if items:
        lines.append(f"\n## 近期事件")
        for item in items:
            date = item.get("date", "")
            text = item.get("text", "")
            tag = item.get("tag", "")
            lines.append(f"- [{date}] {tag}: {text}")
    
    logger.info("数据摘要生成完成", line_count=len(lines))
    return "\n".join(lines)


def build_analysis_prompt(data: Dict, output_dir: str) -> str:
    """
    生成完整的 LLM 分析提示词
    
    包含三个部分:
    1. 市场数据摘要(Markdown格式)
    2. 规则推导结果(已自动计算,无需LLM重复)
    3. 需LLM分析的字段(JSON Schema + 分析要求)
    
    Args:
        data: market_data.json 的完整数据字典
        output_dir: 输出目录路径(用于保存中间文件)
    
    Returns:
        str: 完整的 Markdown 格式提示词
    
    Side Effects:
        - 保存规则推导字段到 output_dir/ai_texts_rules.json
        - 保存事件时间线HTML到 output_dir/event_timeline_auto.html
    
    Example:
        >>> prompt = build_analysis_prompt(data, "./tmp/")
        >>> with open("./tmp/analysis_prompt.md", "w") as f:
        ...     f.write(prompt)
    """
    # 1. 规则推导
    indices = data.get("yesterday", {}).get("indices", [])
    direction_signal = derive_direction_signal(indices)
    direction_judgment = derive_direction_judgment(indices)
    sentiment_class = derive_sentiment_class(data)
    range_low, range_high = derive_sh_range(indices)
    
    # 2. 生成规则字段 JSON
    rule_fields = {
        "DIRECTION_SIGNAL_CLASS": direction_signal,
        "DIRECTION_JUDGMENT": direction_judgment,
        "SENTIMENT_CLASS": sentiment_class,
        "SH_RANGE_LOW": range_low,
        "SH_RANGE_HIGH": range_high,
        "_meta": {
            "derived_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "rules_applied": [
                "direction_signal: avg_pct > 1.0 → bullish, 0.5~1.0 → neutral-bull, etc.",
                "sentiment_class: avg_pct + up_ratio + limit_up → hot/warm/cold/frozen",
                "sh_range: yesterday high/low ± 0.5 * range"
            ]
        }
    }
    
    # 保存规则推导字段
    rule_path = os.path.join(output_dir, "ai_texts_rules.json")
    import json
    with open(rule_path, "w", encoding="utf-8") as f:
        json.dump(rule_fields, f, ensure_ascii=False, indent=2)
    logger.info(f"规则推导字段已保存", path=rule_path)
    
    # 3. 生成数据摘要
    summary = build_data_summary(data)
    
    # 4. 生成 LLM 提示词
    prompt = f"""# 股市早报 LLM 分析请求

> 日期: {data.get('report_date', '')}
> 数据截止: {data.get('data_cutoff', '')}

---

## 市场数据摘要

{summary}

---

## 规则推导结果(已自动计算,无需重复)

| 字段 | 推导值 |
|------|--------|
| DIRECTION_JUDGMENT | {direction_judgment} |
| DIRECTION_SIGNAL_CLASS | {direction_signal} |
| SENTIMENT_CLASS | {sentiment_class} |
| SH_RANGE_LOW | {range_low} |
| SH_RANGE_HIGH | {range_high} |

---

## 需要你分析的字段

请基于以上市场数据,输出以下 JSON 格式的分析结果。**注意:只输出 JSON,不要输出 HTML,HTML 模板由脚本自动渲染。**

### 重磅事件时间线规则

`market_data.news_events.events` 只允许写近期重大国内外事件日历,例如:美联储主席/新主席讲话、美国CPI/PPI/非农、国内LPR/PMI/社融、重要政策会议、AI/半导体/新能源重大发布会。禁止把指数涨跌、北向资金、板块领涨、成交额变化等盘面复盘写入重磅时间线;这些内容应放入昨日回顾、市场温度计或板块方向。若缺少可靠事件日程,必须 WebSearch 验证后补充,不得编造。

```json
{{
  "MARKET_TONE": "市场定调(1-2句话,概括市场特征和关键信号)",
  "EMOTION_FEATURE": "情绪特征(1句话,描述当前市场情绪状态)",
  "US_IMPACT_ON_A": "美股对A股影响判断(2-3句,结合美股涨跌和VIX分析)",
  "GLOBAL_MARKET": "全球市场简析(2-3句,亚太+汇率+大宗商品综合)",
  "GLOBAL_MARKET_ANALYSIS": "全球市场对A股影响分析(1-2句,基于上面数据推导对A股的传导逻辑)",
  "TODAY_PREDICTION": "今日预判(3-4句,结合技术面+消息面+资金面预判今日走势)",
  "YESTERDAY_REVIEW": "昨日回顾补充(2-3句,补充数据表格未涵盖的关键观察)",
  "POSITION_ADVICE": "仓位建议(如:5-6成仓位)",
  "PARTICIPATION_PACE": "参与节奏(一句话,如:低吸不追高,逢分歧布局低位方向)",
  "MENTALITY_ADVICE": ["心态建议条目1", "心态建议条目2", "心态建议条目3"],
  "SIGNALS": [
    {{\"name\": \"补跌完成\", \"status\": \"高位股大幅回调\", \"score\": 8, \"max\": 10}},
    {{\"name\": \"量能放大\", \"status\": \"成交额激增\", \"score\": 9, \"max\": 10}},
    {{\"name\": \"技术支撑\", \"status\": \"关键支撑位站稳\", \"score\": 8, \"max\": 10}},
    {{\"name\": \"情绪回暖\", \"status\": \"赚钱效应强但有分歧\", \"score\": 6, \"max\": 10}},
    {{\"name\": \"资金回流\", \"status\": \"北向资金净流入\", \"score\": 9, \"max\": 10}}
  ],
  "SECTORS": [
    {{\"priority\": 1, \"name\": \"板块名\", \"stars\": \"⭐⭐⭐⭐⭐\", \"logic\": \"核心逻辑"}},
    {{\"priority\": 2, \"name\": \"板块名\", \"stars\": \"⭐⭐⭐⭐\", \"logic\": \"核心逻辑"}}
  ],
  "RISKS": [
    {{\"title\": \"风险1标题\", \"desc\": \"风险1描述"}},
    {{\"title\": \"风险2标题\", \"desc\": \"风险2描述"}}
  ],
  "STRATEGY": [
    {{\"title\": \"仓位控制\", \"desc\": \"描述"}},
    {{\"title\": \"参与节奏\", \"desc\": \"描述"}},
    {{\"title\": \"方向优先\", \"desc\": \"描述"}},
    {{\"title\": \"节奏建议\", \"desc\": \"描述"}}
  ],
  "DISCIPLINES": [
    {{\"title\": \"止损纪律\", \"desc\": \"描述"}},
    {{\"title\": \"仓位纪律\", \"desc\": \"描述"}},
    {{\"title\": \"追涨纪律\", \"desc\": \"描述"}},
    {{\"title\": \"情绪纪律\", \"desc\": \"描述"}}
  ],
  "STYLE_SUMMARY": [
    {{\"icon\": \"💰\", \"title\": \"涨价逻辑优先\", \"desc\": \"描述"}},
    {{\"icon\": \"🔄\", \"title\": \"风格切换确认\", \"desc\": \"描述"}}
  ],
  "STOCKS": [
    {{
      "name": "股票名", "code": "601899", "market_tag": "沪(60)", "market_class": "sh",
      "fund_scores": {{\"业务纯正度\": 9, \"行业地位\": 10, \"涨价受益度\": 8, \"业绩验证\": 8, \"催化剂临近\": 7, \"估值位置\": 6, \"特殊标签\": 7}},
      "tech_scores": {{\"MACD\": 7, \"KDJ\": 5, \"成交量\": 5, \"均线系统\": 4, \"支撑压力\": 3}},
      "logic": {{
        "core": "核心逻辑描述",
        "data": "关键数据描述",
        "catalyst": "催化事件描述",
        "risk": "风险提示描述"
      }}
    }}
  ]
}}
```

### 分析要求

1. **MARKET_TONE**:必须包含关键数据(如突破点位、成交额变化),不含空话
2. **SIGNALS**:5项信号,每项 0-10 分,需结合当日数据具体描述状态
3. **SECTORS**:3-4个板块,优先级排序,逻辑需有数据支撑
4. **RISKS**:至少2项风险,含具体触发条件和影响
5. **STOCKS**:3-5只标的,评分需有依据(三层映射法70分+技术面30分)
6. **选股评分**:每项打分要有逻辑,不要所有股票分数都差不多
7. **POSITION_ADVICE**:与市场判断一致,震荡偏多时仓位5-6成
"""
    
    logger.info("LLM分析提示词生成完成", prompt_length=len(prompt))
    return prompt