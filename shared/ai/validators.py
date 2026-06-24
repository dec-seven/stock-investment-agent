#!/usr/bin/env python3
"""
数据验证工具模块

提供数据完整性验证和安全访问工具函数,用于验证 market_data.json 和 LLM 分析结果的字段完整性。

函数列表:
- validate_required_fields(): 验证必需字段是否存在
- validate_stock_data(): 验证选股数据完整性
- safe_get(): 安全的多层字典访问
"""

import sys
from typing import Any, Dict, List, Optional

# 导入日志
sys.path.insert(0, str(__file__).replace('/shared/ai/validators.py', ''))
from shared.logger import get_logger

logger = get_logger('validators')


def validate_required_fields(data: Dict, required_fields: List[str], context: str = "数据") -> bool:
    """
    验证必需字段是否存在
    
    Args:
        data: 待验证的数据字典
        required_fields: 必需字段列表
        context: 上下文描述(用于错误提示)
    
    Returns:
        bool: 所有字段都存在返回True,否则返回False
    
    Example:
        >>> data = {"name": "test", "value": 123}
        >>> validate_required_fields(data, ["name", "value"], "测试数据")
        True
        >>> validate_required_fields(data, ["name", "missing"], "测试数据")
        False  # 并输出警告日志
    """
    missing = []
    for field in required_fields:
        if field not in data or data[field] is None:
            missing.append(field)
    
    if missing:
        logger.warning(
            f"{context}缺失字段",
            missing_fields=missing,
            context=context
        )
        return False
    
    return True


def validate_stock_data(stock: Dict) -> bool:
    """
    验证选股数据完整性
    
    检查股票数据是否包含必需字段(name, code, fund_scores, tech_scores, logic),
    并验证 fund_scores 和 tech_scores 是否为字典类型。
    
    Args:
        stock: 选股数据字典
    
    Returns:
        bool: 数据完整且格式正确返回True,否则返回False
    
    Example:
        >>> stock = {
        ...     "name": "紫金矿业",
        ...     "code": "601899",
        ...     "fund_scores": {"业务纯正度": 9},
        ...     "tech_scores": {"MACD": 7},
        ...     "logic": {"core": "涨价逻辑"}
        ... }
        >>> validate_stock_data(stock)
        True
    """
    required = ['name', 'code', 'fund_scores', 'tech_scores', 'logic']
    missing = [f for f in required if f not in stock]
    
    if missing:
        name = stock.get('name', stock.get('code', '未知股票'))
        logger.warning(
            f"选股数据缺失字段",
            stock=name,
            missing_fields=missing
        )
        return False
    
    # 验证 fund_scores 和 tech_scores 是字典
    if not isinstance(stock.get('fund_scores'), dict):
        logger.warning(
            f"选股数据格式错误",
            stock=stock.get('name', '未知'),
            field='fund_scores',
            expected_type='dict',
            actual_type=str(type(stock.get('fund_scores')))
        )
        return False
    
    if not isinstance(stock.get('tech_scores'), dict):
        logger.warning(
            f"选股数据格式错误",
            stock=stock.get('name', '未知'),
            field='tech_scores',
            expected_type='dict',
            actual_type=str(type(stock.get('tech_scores')))
        )
        return False
    
    return True


def safe_get(data: Any, *keys: str, default: Any = None) -> Any:
    """
    安全的多层字典访问
    
    避免多层字典访问时的 KeyError 和 TypeError,如果任意层级访问失败则返回默认值。
    
    Args:
        data: 待访问的数据(可以是字典或其他类型)
        *keys: 访问路径中的键名序列
        default: 访问失败时的默认返回值
    
    Returns:
        Any: 访问成功返回目标值,失败返回default
    
    Example:
        >>> data = {"a": {"b": {"c": 123}}}
        >>> safe_get(data, "a", "b", "c")
        123
        >>> safe_get(data, "a", "missing", "c", default="未找到")
        '未找到'
        >>> safe_get(None, "a", "b")
        None
    """
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, default)
        else:
            return default
    return data
