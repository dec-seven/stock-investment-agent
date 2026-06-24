#!/usr/bin/env python3
"""
HTML 模板构建模块

提供 12 个 build_* 函数用于生成早报各模块的 HTML 片段。
所有函数基于结构化数据渲染 HTML,不依赖 LLM。

函数列表:
- build_signal_monitor_html(): 见底信号监控表格
- build_mentality_html(): 心态管理模块
- build_discipline_html(): 操作纪律条目
- build_risk_warnings_html(): 风险提示
- build_strategy_html(): 操作策略
- build_sector_table_html(): 板块方向表格
- build_style_summary_html(): 方法论沉淀
- build_stock_card_html(): 单只选股卡片
- build_stock_cards_html(): 全部选股卡片
- build_event_timeline_html(): 事件时间线
- _build_score_bar_row(): 单行评分条(内部函数)
"""

import sys
from typing import Dict, List

# 导入日志和验证工具
sys.path.insert(0, str(__file__).replace('/shared/ai/html_builders.py', ''))
from shared.logger import get_logger
from shared.ai.validators import validate_stock_data
from shared.ai.insight_engine import derive_sentiment_label

logger = get_logger('html_builders')


def build_signal_monitor_html(signals: List[Dict]) -> str:
    """
    生成见底信号监控表格 HTML
    
    渲染5项见底信号的评分表格,包含信号名称、状态、评分,以及综合评分。
    评分颜色规则:
    - ≥70%: 绿色(#69f0ae) + ✅
    - ≥40%: 黄色(#ffd740) + ⚠️
    - <40%: 红色(#ff5252) + ❌
    
    Args:
        signals: 信号数据列表,每项包含 name, status, score, max 字段
    
    Returns:
        str: 完整的 HTML 表格字符串
    
    Example:
        >>> signals = [
        ...     {"name": "补跌完成", "status": "高位股大幅回调", "score": 8, "max": 10},
        ...     {"name": "量能放大", "status": "成交额激增", "score": 9, "max": 10}
        ... ]
        >>> html = build_signal_monitor_html(signals)
    """
    if not signals:
        logger.warning("信号数据为空,返回空表格")
        return '<table class="data-table scoring-table"><thead><tr><th>信号</th><th>状态</th><th>评分</th></tr></thead><tbody><tr><td colspan="3">暂无信号数据</td></tr></tbody></table>'
    
    rows = ""
    total_score = 0
    max_score = 0
    
    for sig in signals:
        name = sig.get("name", "")
        status = sig.get("status", "")
        score = sig.get("score", 0)
        max_s = sig.get("max", 10)
        total_score += score
        max_score += max_s
        
        # 评分颜色
        ratio = score / max_s if max_s > 0 else 0
        if ratio >= 0.7:
            score_color = "#69f0ae"
            status_icon = "✅"
        elif ratio >= 0.4:
            score_color = "#ffd740"
            status_icon = "⚠️"
        else:
            score_color = "#ff5252"
            status_icon = "❌"
        
        rows += f'<tr><td>{name}</td><td>{status_icon} {status}</td><td style="color:{score_color}">{score}/{max_s}</td></tr>'
    
    # 综合评分颜色
    total_ratio = total_score / max_score if max_score > 0 else 0
    if total_ratio >= 0.7:
        total_color = "#69f0ae"
        label = "信号充足"
    elif total_ratio >= 0.4:
        total_color = "#ffd740"
        label = "信号一般"
    else:
        total_color = "#ff5252"
        label = "信号不足"
    
    html = '<table class="data-table scoring-table">'
    html += '<thead><tr><th>信号</th><th>状态</th><th>评分</th></tr></thead>'
    html += f'<tbody>{rows}</tbody>'
    html += f'<tfoot><tr><td colspan="2" style="text-align:right">综合评分</td><td style="color:{total_color};font-weight:700">{total_score}/{max_score} · {label}</td></tr></tfoot>'
    html += '</table>'
    
    logger.info("见底信号表格渲染完成", signal_count=len(signals), total_score=total_score)
    return html


def build_mentality_html(sentiment_class: str, advice_lines: List[str]) -> str:
    """
    生成心态管理模块 HTML
    
    基于情绪色彩类和心态建议生成心态管理卡片。
    
    Args:
        sentiment_class: 情绪色彩类名(如 sentiment-hot)
        advice_lines: 心态建议条目列表(3-5条)
    
    Returns:
        str: 完整的 HTML div 字符串
    
    Example:
        >>> html = build_mentality_html("sentiment-warm", ["低吸不追高", "逢分歧布局低位方向"])
    """
    label = derive_sentiment_label(sentiment_class)
    advice_html = "<br>".join([f"{'①②③④⑤'[i]} {line}" for i, line in enumerate(advice_lines)])
    
    html = f'<div class="mentality-box {sentiment_class}"><div class="mentality-stage">{label}</div><div class="advice">{advice_html}</div></div>'
    
    logger.info("心态管理模块渲染完成", sentiment_class=sentiment_class, advice_count=len(advice_lines))
    return html


def build_discipline_html(items: List[Dict]) -> str:
    """
    生成操作纪律条目 HTML
    
    渲染操作纪律列表(通常4条:止损、仓位、追涨、情绪纪律)。
    
    Args:
        items: 纪律条目列表,每项包含 title 和 desc 字段
    
    Returns:
        str: HTML li 元素列表(不含外层 ul)
    
    Example:
        >>> items = [{"title": "止损纪律", "desc": "跌破支撑位立即止损"}]
        >>> html = build_discipline_html(items)
    """
    html = ""
    for item in items:
        title = item.get("title", "")
        desc = item.get("desc", "")
        html += f'<li><b>{title}</b>：{desc}</li>'
    
    logger.info("操作纪律条目渲染完成", discipline_count=len(items))
    return html


def build_risk_warnings_html(risks: List[Dict]) -> str:
    """
    生成风险提示 HTML
    
    渲染风险提示卡片(通常2-3条)。
    
    Args:
        risks: 风险条目列表,每项包含 title 和 desc 字段
    
    Returns:
        str: HTML div 卡片列表
    
    Example:
        >>> risks = [{"title": "美股波动风险", "desc": "VIX指数上升可能导致A股承压"}]
        >>> html = build_risk_warnings_html(risks)
    """
    html = ""
    for i, risk in enumerate(risks, 1):
        title = risk.get("title", f"风险{i}")
        desc = risk.get("desc", "")
        html += f'<div class="risk-box"><div class="risk-title">⚠️ {title}</div><div class="risk-desc">{desc}</div></div>'
    
    logger.info("风险提示渲染完成", risk_count=len(risks))
    return html


def build_strategy_html(items: List[Dict]) -> str:
    """
    生成操作策略 HTML
    
    渲染操作策略列表(通常4条:仓位控制、参与节奏、方向优先、节奏建议)。
    
    Args:
        items: 策略条目列表,每项包含 title 和 desc 字段
    
    Returns:
        str: 完整的 HTML ul 字符串
    
    Example:
        >>> items = [{"title": "仓位控制", "desc": "5-6成仓位"}]
        >>> html = build_strategy_html(items)
    """
    html = '<ul class="strategy-list">'
    for item in items:
        title = item.get("title", "")
        desc = item.get("desc", "")
        html += f'<li><b>{title}</b>：{desc}</li>'
    html += '</ul>'
    
    logger.info("操作策略渲染完成", strategy_count=len(items))
    return html


def build_sector_table_html(sectors: List[Dict]) -> str:
    """
    生成板块方向表格 HTML
    
    渲染板块方向表格(通常3-4个板块),包含优先级、板块名、星级、核心逻辑。
    
    Args:
        sectors: 板块数据列表,每项包含 priority, name, stars, logic 字段
    
    Returns:
        str: 完整的 HTML 表格字符串
    
    Example:
        >>> sectors = [{"priority": 1, "name": "黄金", "stars": "⭐⭐⭐⭐⭐", "logic": "避险情绪升温"}]
        >>> html = build_sector_table_html(sectors)
    """
    rows = ""
    for s in sectors:
        priority = s.get("priority", "")
        name = s.get("name", "")
        stars = s.get("stars", "⭐⭐⭐")
        logic = s.get("logic", "")
        rows += f'<tr><td>{priority}</td><td>{name}</td><td class="star">{stars}</td><td>{logic}</td></tr>'
    
    html = '<table class="data-table sector-table">'
    html += '<thead><tr><th>优先级</th><th>板块方向</th><th>星级</th><th>核心逻辑</th></tr></thead>'
    html += f'<tbody>{rows}</tbody>'
    html += '</table>'
    
    logger.info("板块方向表格渲染完成", sector_count=len(sectors))
    return html


def build_style_summary_html(items: List[Dict]) -> str:
    """
    生成方法论沉淀 HTML
    
    渲染方法论沉淀列表(通常2-3条)。
    
    Args:
        items: 方法论条目列表,每项包含 icon, title, desc 字段
    
    Returns:
        str: 完整的 HTML ul 字符串
    
    Example:
        >>> items = [{"icon": "💰", "title": "涨价逻辑优先", "desc": "优先选择涨价受益标的"}]
        >>> html = build_style_summary_html(items)
    """
    html = '<ul class="style-summary-list">'
    for item in items:
        icon = item.get("icon", "💡")
        title = item.get("title", "")
        desc = item.get("desc", "")
        html += f'<li>{icon} <b>{title}</b>：{desc}</li>'
    html += '</ul>'
    
    logger.info("方法论沉淀渲染完成", item_count=len(items))
    return html


def _build_score_bar_row(label: str, val: int, max_val: int) -> str:
    """
    生成单行评分条 HTML
    
    内部函数,用于渲染评分条的单行,包含标签、进度条、分数。
    
    Args:
        label: 评分维度名称
        val: 实际得分
        max_val: 最高分
    
    Returns:
        str: 单行评分条 HTML
    
    Example:
        >>> html = _build_score_bar_row("业务纯正度", 9, 10)
    """
    pct = val / max_val * 100 if max_val > 0 else 0
    if pct >= 70:
        cls = "good"
    elif pct >= 40:
        cls = "mid"
    else:
        cls = "bad"
    
    return f'<div class="score-bar-row"><span class="score-bar-label">{label}</span><div class="score-bar-track"><div class="score-bar-fill {cls}" style="width:{pct:.0f}%"></div></div><span class="score-bar-val {cls}">{val}/{max_val}</span></div>'


def build_stock_card_html(stock: Dict) -> str:
    """
    生成单只选股卡片 HTML
    
    渲染完整的选股卡片,包含股票基本信息、评分条(v3样式)、核心逻辑。
    评分条包含三层映射法7项(满分70)+技术面5项(满分30),总分100。
    
    Args:
        stock: 选股数据字典,包含:
            - name: 股票名称
            - code: 股票代码
            - market_tag: 市场标签(如"沪(60)")
            - market_class: 市场样式类(如"sh")
            - fund_scores: 三层映射法评分(dict)
            - tech_scores: 技术面评分(dict)
            - logic: 核心逻辑(dict,包含 core/data/catalyst/risk)
    
    Returns:
        str: 完整的 HTML div 卡片字符串
    
    Example:
        >>> stock = {
        ...     "name": "紫金矿业",
        ...     "code": "601899",
        ...     "market_tag": "沪(60)",
        ...     "market_class": "sh",
        ...     "fund_scores": {"业务纯正度": 9},
        ...     "tech_scores": {"MACD": 7},
        ...     "logic": {"core": "涨价逻辑"}
        ... }
        >>> html = build_stock_card_html(stock)
    """
    # 数据完整性验证
    if not validate_stock_data(stock):
        logger.warning(f"选股数据不完整,返回错误卡片", stock=stock.get('name', '未知'))
        return '<div class="stock-card error">数据不完整</div>'
    
    name = stock.get("name", "")
    code = stock.get("code", "")
    market_tag = stock.get("market_tag", "")
    market_class = stock.get("market_class", "sz")
    
    # 评分条
    fund_scores = stock.get("fund_scores", {})
    tech_scores = stock.get("tech_scores", {})
    
    fund_total = sum(v for v in fund_scores.values()) if fund_scores else 0
    tech_total = sum(v for v in tech_scores.values()) if tech_scores else 0
    total_score = fund_total + tech_total
    
    # 评级
    if total_score >= 85:
        rating = "⭐⭐⭐⭐⭐ 强烈推荐"
    elif total_score >= 75:
        rating = "⭐⭐⭐⭐ 推荐"
    elif total_score >= 60:
        rating = "⭐⭐⭐ 一般观察"
    else:
        rating = "⭐⭐ 不建议"
    
    # 评分条HTML
    score_bars_html = ""
    
    # 映射法7项
    fund_dims = [
        ("业务纯正度", 10), ("行业地位", 10), ("涨价受益度", 10),
        ("业绩验证", 10), ("催化剂临近", 10), ("估值位置", 10), ("特殊标签", 10)
    ]
    for dim, max_s in fund_dims:
        val = fund_scores.get(dim, 0)
        score_bars_html += _build_score_bar_row(dim, val, max_s)
    
    # 技术面5项
    tech_dims = [
        ("MACD", 8), ("KDJ", 7), ("成交量", 6), ("均线系统", 5), ("支撑压力", 4)
    ]
    for dim, max_s in tech_dims:
        val = tech_scores.get(dim, 0)
        score_bars_html += _build_score_bar_row(dim, val, max_s)
    
    # 核心逻辑
    logic = stock.get("logic", {})
    logic_html = ""
    for key, label, color in [
        ("core", "核心逻辑", "var(--blue-accent)"),
        ("data", "关键数据", "var(--blue-accent)"),
        ("catalyst", "催化事件", "var(--blue-accent)"),
        ("risk", "风险提示", "#ff5252"),
    ]:
        if key in logic and logic[key]:
            logic_html += f'<span class="label" style="color:{color}">{label}：</span>{logic[key]}<br>'
    
    html = f'''<div class="stock-card">
  <div class="stock-header">
    <span class="stock-name">{name}</span>
    <span class="stock-code">{code}</span>
    <span class="stock-market {market_class}">{market_tag}</span>
    <div class="stock-total-score">
      <div class="score-val">{total_score}</div>
      <div class="score-label">总分 / 100</div>
      <div class="stock-stars">{rating}</div>
    </div>
  </div>
  <div class="score-bars">{score_bars_html}</div>
  <div class="score-summary">
    <div class="sum-item"><span class="sum-label">三层映射:</span><span class="sum-val-fund">{fund_total}/70</span></div>
    <span class="sum-divider">|</span>
    <div class="sum-item"><span class="sum-label">技术面:</span><span class="sum-val-tech">{tech_total}/30</span></div>
  </div>
  <div class="stock-logic">{logic_html}</div>
</div>'''
    
    logger.info(f"选股卡片渲染完成", stock=name, total_score=total_score, rating=rating.split()[0])
    return html


def build_stock_cards_html(stocks: List[Dict]) -> str:
    """
    生成全部选股卡片 HTML
    
    验证所有选股数据并渲染卡片列表,无效数据跳过并记录警告。
    
    Args:
        stocks: 选股数据列表
    
    Returns:
        str: 完整的 HTML div 卡片容器字符串
    
    Example:
        >>> stocks = [{"name": "紫金矿业", "code": "601899", ...}]
        >>> html = build_stock_cards_html(stocks)
    """
    if not stocks:
        logger.warning("选股列表为空,返回空提示")
        return '<div class="no-data">暂无选股推荐</div>'
    
    cards = ""
    valid_count = 0
    
    for s in stocks:
        if validate_stock_data(s):
            cards += build_stock_card_html(s)
            valid_count += 1
        else:
            name = s.get('name', s.get('code', '未知'))
            logger.warning(f"跳过无效选股", stock=name)
    
    if valid_count == 0:
        logger.warning("无有效选股数据,返回空提示")
        return '<div class="no-data">无有效选股数据</div>'
    
    logger.info(f"选股卡片列表渲染完成", valid_count=valid_count, invalid_count=len(stocks) - valid_count)
    return f'<div class="stock-cards">{cards}</div>'


def build_event_timeline_html(events: List[Dict]) -> str:
    """
    生成事件时间线 HTML
    
    渲染重大事件时间线(近期国内外重要事件日历)。
    
    Args:
        events: 事件数据列表,每项包含 date, text, tag, css_class 字段
    
    Returns:
        str: 完整的 HTML div 时间线字符串
    
    Example:
        >>> events = [{"date": "06-25", "text": "美联储主席讲话", "tag": "重磅", "css_class": "tag-important"}]
        >>> html = build_event_timeline_html(events)
    """
    if not events:
        logger.warning("事件数据为空,返回空时间线")
        return '<div class="timeline"><div class="timeline-item"><span class="timeline-text">暂无重大事件</span></div></div>'
    
    html = '<div class="timeline">\n'
    for ev in events:
        date = ev.get("date", "")
        text = ev.get("text", "")
        tag = ev.get("tag", "")
        css_class = ev.get("css_class", "tag-normal")
        tag_html = f'<span class="timeline-tag {css_class}">{tag}</span>' if tag else ""
        html += f'    <div class="timeline-item">\n'
        html += f'        <div class="timeline-date">{date}</div>\n'
        html += f'        <div class="timeline-content">{tag_html}{text}</div>\n'
        html += f'    </div>\n'
    html += '</div>'
    
    logger.info("事件时间线渲染完成", event_count=len(events))
    return html