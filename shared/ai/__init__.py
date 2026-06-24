#!/usr/bin/env python3
"""
AI 模块

提供 LLM 相关的工具函数,包括数据验证、规则推导、HTML构建、提示词构建、编译和响应解析。

模块列表:
- validators: 数据验证工具
- insight_engine: 市场洞察推导引擎
- html_builders: HTML 模板构建
- prompt_builder: LLM 分析提示词构建
- compiler: AI 文本编译
- response_parser: LLM 响应解析
"""

from .validators import validate_required_fields, validate_stock_data, safe_get
from .insight_engine import (
    derive_direction_signal,
    derive_direction_judgment,
    derive_sentiment_class,
    derive_sentiment_label,
    derive_sh_range
)
from .html_builders import (
    build_signal_monitor_html,
    build_mentality_html,
    build_discipline_html,
    build_risk_warnings_html,
    build_strategy_html,
    build_sector_table_html,
    build_style_summary_html,
    build_stock_card_html,
    build_stock_cards_html,
    build_event_timeline_html
)
from .prompt_builder import build_data_summary, build_analysis_prompt
from .compiler import compile_ai_texts
from .response_parser import parse_llm_response, validate_llm_json

__all__ = [
    # validators
    'validate_required_fields',
    'validate_stock_data',
    'safe_get',
    
    # insight_engine
    'derive_direction_signal',
    'derive_direction_judgment',
    'derive_sentiment_class',
    'derive_sentiment_label',
    'derive_sh_range',
    
    # html_builders
    'build_signal_monitor_html',
    'build_mentality_html',
    'build_discipline_html',
    'build_risk_warnings_html',
    'build_strategy_html',
    'build_sector_table_html',
    'build_style_summary_html',
    'build_stock_card_html',
    'build_stock_cards_html',
    'build_event_timeline_html',
    
    # prompt_builder
    'build_data_summary',
    'build_analysis_prompt',
    
    # compiler
    'compile_ai_texts',
    
    # response_parser
    'parse_llm_response',
    'validate_llm_json',
]
