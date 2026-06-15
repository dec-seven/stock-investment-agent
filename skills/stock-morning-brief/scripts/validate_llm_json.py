#!/usr/bin/env python3
"""
LLM 分析 JSON 格式验证脚本

用法:
  python3 validate_llm_json.py --input ./tmp/llm_analysis.json

验证项:
  1. JSON 格式合法性
  2. 必需字段完整性
  3. 字段类型正确性
  4. 选股数据结构
"""
import json
import sys
import argparse
from pathlib import Path


# 必需字段定义
REQUIRED_FIELDS = {
    # 纯文本字段
    "MARKET_TONE": {"type": str, "desc": "市场定调"},
    "EMOTION_FEATURE": {"type": str, "desc": "情绪特征"},
    "US_IMPACT_ON_A": {"type": str, "desc": "美股对A股影响"},
    "GLOBAL_MARKET": {"type": str, "desc": "全球市场"},
    "GLOBAL_MARKET_ANALYSIS": {"type": str, "desc": "全球市场对A股影响分析"},
    "TODAY_PREDICTION": {"type": str, "desc": "今日预判"},
    "YESTERDAY_REVIEW": {"type": str, "desc": "昨日回顾"},
    "POSITION_ADVICE": {"type": str, "desc": "仓位建议"},
    "PARTICIPATION_PACE": {"type": str, "desc": "参与节奏"},
    
    # 数组字段
    "SIGNALS": {"type": list, "desc": "见底信号"},
    "SECTORS": {"type": list, "desc": "板块方向"},
    "RISKS": {"type": list, "desc": "风险提示"},
    "STRATEGY": {"type": list, "desc": "操作策略"},
    "DISCIPLINES": {"type": list, "desc": "操作纪律"},
    "STYLE_SUMMARY": {"type": list, "desc": "方法论沉淀"},
    "MENTALITY_ADVICE": {"type": list, "desc": "心态管理"},
    "STOCKS": {"type": list, "desc": "选股推荐"},
}

# 选股必需字段
REQUIRED_STOCK_FIELDS = {
    "name": {"type": str, "desc": "股票名称"},
    "code": {"type": str, "desc": "股票代码"},
    "market_tag": {"type": str, "desc": "市场标签"},
    "market_class": {"type": str, "desc": "市场样式类"},
    "fund_scores": {"type": dict, "desc": "基本面评分"},
    "tech_scores": {"type": dict, "desc": "技术面评分"},
    "logic": {"type": dict, "desc": "核心逻辑"},
}


def validate_json_file(filepath):
    """验证 JSON 文件"""
    errors = []
    warnings = []
    
    # 1. 文件存在性检查
    if not Path(filepath).exists():
        errors.append(f"文件不存在: {filepath}")
        return errors, warnings
    
    # 2. JSON 格式检查
    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"JSON 格式错误: {e}")
        return errors, warnings
    except Exception as e:
        errors.append(f"文件读取错误: {e}")
        return errors, warnings
    
    # 3. 必需字段检查
    missing_fields = []
    for field, config in REQUIRED_FIELDS.items():
        if field not in data:
            missing_fields.append(field)
        elif not isinstance(data[field], config["type"]):
            expected_type = config["type"].__name__
            actual_type = type(data[field]).__name__
            errors.append(f"字段 '{field}' 类型错误: 期望 {expected_type}, 实际 {actual_type}")
    
    if missing_fields:
        errors.append(f"缺失字段: {', '.join(missing_fields)}")
    
    # 4. 数组字段非空检查
    for field in ["SIGNALS", "SECTORS", "STOCKS"]:
        if field in data and isinstance(data[field], list):
            if len(data[field]) == 0:
                warnings.append(f"字段 '{field}' 为空数组")
    
    # 5. 选股数据结构检查
    if "STOCKS" in data and isinstance(data["STOCKS"], list):
        for i, stock in enumerate(data["STOCKS"]):
            stock_errors = validate_stock(stock, i)
            errors.extend(stock_errors)
    
    return errors, warnings


def validate_stock(stock, index):
    """验证单个选股数据"""
    errors = []
    stock_name = stock.get("name", stock.get("code", f"#{index+1}"))
    
    for field, config in REQUIRED_STOCK_FIELDS.items():
        if field not in stock:
            errors.append(f"选股 '{stock_name}' 缺失字段: {field}")
        elif not isinstance(stock.get(field), config["type"]):
            expected_type = config["type"].__name__
            actual_type = type(stock.get(field)).__name__
            errors.append(f"选股 '{stock_name}' 字段 '{field}' 类型错误: 期望 {expected_type}, 实际 {actual_type}")
    
    # 验证评分完整性
    if "fund_scores" in stock and isinstance(stock["fund_scores"], dict):
        expected_fund_dims = ["业务纯正度", "行业地位", "涨价受益度", "业绩验证", "催化剂临近", "估值位置", "特殊标签"]
        missing_dims = [d for d in expected_fund_dims if d not in stock["fund_scores"]]
        if missing_dims:
            errors.append(f"选股 '{stock_name}' fund_scores 缺失维度: {', '.join(missing_dims)}")
    
    if "tech_scores" in stock and isinstance(stock["tech_scores"], dict):
        expected_tech_dims = ["MACD", "KDJ", "成交量", "均线系统", "支撑压力"]
        missing_dims = [d for d in expected_tech_dims if d not in stock["tech_scores"]]
        if missing_dims:
            errors.append(f"选股 '{stock_name}' tech_scores 缺失维度: {', '.join(missing_dims)}")
    
    # 验证逻辑字段
    if "logic" in stock and isinstance(stock["logic"], dict):
        expected_logic_keys = ["core", "data", "catalyst", "risk"]
        missing_keys = [k for k in expected_logic_keys if k not in stock["logic"]]
        if missing_keys:
            errors.append(f"选股 '{stock_name}' logic 缺失键: {', '.join(missing_keys)}")
    
    return errors


def main():
    parser = argparse.ArgumentParser(description="LLM 分析 JSON 格式验证")
    parser.add_argument("--input", required=True, help="llm_analysis.json 路径")
    args = parser.parse_args()
    
    print(f"[INFO] 验证文件: {args.input}")
    errors, warnings = validate_json_file(args.input)
    
    # 输出结果
    if warnings:
        print("\n[WARNINGS]")
        for w in warnings:
            print(f"  ⚠️  {w}")
    
    if errors:
        print("\n[ERRORS]")
        for e in errors:
            print(f"  ❌ {e}")
        print(f"\n[FAILED] 发现 {len(errors)} 个错误")
        sys.exit(1)
    else:
        print("\n[SUCCESS] JSON 格式验证通过 ✅")
        sys.exit(0)


if __name__ == "__main__":
    main()
