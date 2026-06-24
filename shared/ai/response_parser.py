#!/usr/bin/env python3
"""
LLM 响应解析模块

解析 LLM 返回的 JSON 响应并进行校验,确保数据格式正确。
新增模块,用于规范 LLM 响应处理流程。

函数列表:
- parse_llm_response(): 解析 LLM 响应为 JSON 字典
- validate_llm_json(): 验证 LLM 分析 JSON 的必需字段
"""

import sys
import json
from typing import Dict, List, Optional

# 导入日志
sys.path.insert(0, str(__file__).replace('/shared/ai/response_parser.py', ''))
from shared.logger import get_logger

logger = get_logger('response_parser')


def parse_llm_response(response_text: str) -> Optional[Dict]:
    """
    解析 LLM 响应为 JSON 字典
    
    处理 LLM 返回的文本响应,提取其中的 JSON 内容。
    支持三种格式:
    1. 纯 JSON 文本
    2. 包含在 ```json ... ``` 代码块中的 JSON
    3. 包含在 ``` ... ``` 代码块中的 JSON
    
    Args:
        response_text: LLM 返回的原始文本
    
    Returns:
        Optional[Dict]: 解析成功的 JSON 字典,失败返回 None
    
    Example:
        >>> response = '{"MARKET_TONE": "市场震荡上行", "SIGNALS": []}'
        >>> data = parse_llm_response(response)
        >>> print(data["MARKET_TONE"])
        '市场震荡上行'
    """
    # 尝试直接解析
    try:
        data = json.loads(response_text)
        logger.info("LLM响应直接解析成功", response_length=len(response_text))
        return data
    except json.JSONDecodeError:
        pass
    
    # 尝试提取 ```json ... ``` 代码块
    if "```json" in response_text:
        start = response_text.find("```json") + len("```json")
        end = response_text.find("```", start)
        if end > start:
            json_text = response_text[start:end].strip()
            try:
                data = json.loads(json_text)
                logger.info("从json代码块提取成功", json_length=len(json_text))
                return data
            except json.JSONDecodeError as e:
                logger.error("json代码块解析失败", error=str(e))
    
    # 尝试提取 ``` ... ``` 代码块
    if "```" in response_text:
        start = response_text.find("```") + len("```")
        end = response_text.find("```", start)
        if end > start:
            json_text = response_text[start:end].strip()
            try:
                data = json.loads(json_text)
                logger.info("从代码块提取成功", json_length=len(json_text))
                return data
            except json.JSONDecodeError as e:
                logger.error("代码块解析失败", error=str(e))
    
    logger.error("LLM响应解析失败", response_preview=response_text[:200])
    return None


def validate_llm_json(data: Dict, required_fields: List[str] = None) -> bool:
    """
    验证 LLM 分析 JSON 的必需字段
    
    检查 LLM 返回的 JSON 是否包含所有必需字段,并验证关键字段的格式。
    
    Args:
        data: LLM 分析结果字典
        required_fields: 必需字段列表,默认为标准的早报分析字段
    
    Returns:
        bool: 所有必需字段存在且格式正确返回 True,否则返回 False
    
    Example:
        >>> data = {"MARKET_TONE": "市场震荡", "SIGNALS": [], "SECTORS": []}
        >>> validate_llm_json(data)
        False  # 缺少 STOCKS 等必需字段
    """
    if required_fields is None:
        required_fields = [
            "MARKET_TONE", "EMOTION_FEATURE", "US_IMPACT_ON_A",
            "TODAY_PREDICTION", "SIGNALS", "SECTORS", "STOCKS"
        ]
    
    # 检查必需字段
    missing = []
    for field in required_fields:
        if field not in data or data[field] is None:
            missing.append(field)
    
    if missing:
        logger.warning("LLM分析缺少必需字段", missing_fields=missing)
        return False
    
    # 验证数组字段格式
    array_fields = ["SIGNALS", "SECTORS", "STOCKS", "RISKS", "STRATEGY", "DISCIPLINES"]
    for field in array_fields:
        if field in data and not isinstance(data[field], list):
            logger.warning(f"字段格式错误", field=field, expected_type="list", actual_type=str(type(data[field])))
            return False
    
    # 验证 SIGNALS 结构
    if "SIGNALS" in data and data["SIGNALS"]:
        for i, sig in enumerate(data["SIGNALS"]):
            if not all(k in sig for k in ["name", "status", "score", "max"]):
                logger.warning(f"SIGNALS[{i}] 缺少必需字段", signal=sig)
                return False
    
    # 验证 STOCKS 结构
    if "STOCKS" in data and data["STOCKS"]:
        for i, stock in enumerate(data["STOCKS"]):
            required_stock_fields = ["name", "code", "fund_scores", "tech_scores", "logic"]
            if not all(k in stock for k in required_stock_fields):
                logger.warning(f"STOCKS[{i}] 缺少必需字段", stock=stock.get("name", f"股票{i}"))
                return False
    
    logger.info("LLM分析JSON验证通过", field_count=len(required_fields))
    return True
