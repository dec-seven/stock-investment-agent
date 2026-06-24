#!/usr/bin/env python3
"""
数据验证脚本：检测价格异常、数据缺失、逻辑错误
用法: python3 validate_market_data.py --data ./tmp/market_data.json
"""

import json
import sys
import argparse
from datetime import datetime, timedelta


# ==================== 合理价格范围 ====================
# 格式: (最小值, 最大值, 允许偏差%)
PRICE_RANGES = {
    # A股指数
    "上证指数": (2500, 6000, 20),      # 历史范围约 2500-6000
    "深证成指": (8000, 20000, 20),
    "创业板指": (1500, 5000, 20),
    "科创50": (800, 2500, 20),
    "北证50": (500, 2000, 20),
    "上证50": (1800, 4000, 20),
    "沪深300": (2500, 6000, 20),

    # 美股
    "道琼斯": (20000, 60000, 30),
    "标普500": (3000, 10000, 30),
    "纳斯达克": (8000, 30000, 30),
    "VIX恐慌指数": (10, 50, 50),        # VIX 波动较大
    "费城半导体": (2000, 10000, 30),
    "英伟达": (100, 300, 40),
    "特斯拉": (100, 500, 40),
    "WTI原油": (30, 150, 40),
    "COMEX黄金": (1800, 5000, 30),

    # 全球市场
    "日经225": (20000, 80000, 30),
    "恒生指数": (15000, 35000, 30),
    "美元指数DXY": (80, 120, 10),
    "离岸人民币": (6.0, 8.0, 5),
}


def validate_price(name, close, pct, source="unknown"):
    """验证单个品种的价格和涨跌幅"""
    errors = []

    # 1. 检查价格范围
    if name in PRICE_RANGES:
        min_price, max_price, tolerance = PRICE_RANGES[name]
        if close < min_price * (1 - tolerance/100):
            errors.append(f"⚠️ {name} 价格过低: {close:.2f} < {min_price*(1-tolerance/100):.2f}")
        if close > max_price * (1 + tolerance/100):
            errors.append(f"⚠️ {name} 价格过高: {close:.2f} > {max_price*(1+tolerance/100):.2f}")

    # 2. 检查涨跌幅合理性
    if abs(pct) > 20:
        errors.append(f"⚠️ {name} 涨跌幅异常: {pct:+.2f}% (超过±20%)")

    # 3. 检查数据来源
    if source == "websearch":
        # WebSearch 数据需要额外验证
        pass

    return errors


def validate_market_data(data):
    """验证整个 market_data.json"""
    all_errors = []

    print("\n=== 数据验证报告 ===\n")

    # 1. 验证 A股指数
    print("【A股指数】")
    indices = data.get("yesterday", {}).get("indices", [])
    for idx in indices:
        name = idx.get("name", "未知")
        close = idx.get("close")
        pct = idx.get("pct", 0)
        source = idx.get("source", "unknown")

        if close is None:
            all_errors.append(f"❌ {name} 缺少收盘价数据")
            print(f"  {name}: ❌ 缺少数据")
            continue

        errors = validate_price(name, close, pct, source)
        all_errors.extend(errors)

        if errors:
            for e in errors:
                print(f"  {e}")
        else:
            print(f"  {name}: {close:,.2f} ({pct:+.2f}%) ✅ source={source}")

    # 2. 验证美股数据
    print("\n【美股与大宗商品】")
    us_data = data.get("overnight_us", {})
    for key, item in us_data.items():
        name = item.get("name", key)
        close = item.get("close")
        pct = item.get("pct", 0)
        source = item.get("source", "unknown")

        if close is None:
            all_errors.append(f"❌ {name} 缺少收盘价数据")
            print(f"  {name}: ❌ 缺少数据")
            continue

        # 特殊处理名称映射
        if key == "gold":
            name = "COMEX黄金"
        elif key == "oil":
            name = "WTI原油"

        errors = validate_price(name, close, pct, source)
        all_errors.extend(errors)

        if errors:
            for e in errors:
                print(f"  {e}")
        else:
            print(f"  {name}: {close:,.2f} ({pct:+.2f}%) ✅ source={source}")

    # 3. 验证全球市场
    print("\n【全球市场】")
    global_markets = data.get("global_markets", {})
    for key, item in global_markets.items():
        name = item.get("name", key)
        close = item.get("close")
        pct = item.get("pct", 0)
        source = item.get("source", "unknown")

        if close is None:
            all_errors.append(f"❌ {name} 缺少收盘价数据")
            print(f"  {name}: ❌ 缺少数据")
            continue

        errors = validate_price(name, close, pct, source)
        all_errors.extend(errors)

        if errors:
            for e in errors:
                print(f"  {e}")
        else:
            print(f"  {name}: {close:,.2f} ({pct:+.2f}%) ✅ source={source}")

    # 4. 验证市场广度
    print("\n【市场广度】")
    breadth = data.get("yesterday", {}).get("market_breadth", {})
    up = breadth.get("up_count", 0)
    down = breadth.get("down_count", 0)
    total = up + down

    if total > 0:
        up_ratio = up / total
        if up_ratio > 0.9:
            all_errors.append(f"⚠️ 上涨家数占比过高: {up_ratio:.1%}")
        elif up_ratio < 0.1:
            all_errors.append(f"⚠️ 下跌家数占比过高: {1-up_ratio:.1%}")
        print(f"  上涨/下跌: {up} / {down} ({up_ratio:.1%}) ✅")
    else:
        all_errors.append("❌ 缺少涨跌家数数据")

    # 5. 汇总报告
    print("\n" + "="*50)
    if all_errors:
        print(f"⚠️ 发现 {len(all_errors)} 个问题：")
        for e in all_errors:
            print(f"  {e}")
        print("\n建议：检查数据来源，必要时重新获取数据")
        return False
    else:
        print("✅ 所有数据验证通过")
        return True


def main():
    parser = argparse.ArgumentParser(description="验证市场数据合理性")
    parser.add_argument("--data", required=True, help="market_data.json 路径")
    args = parser.parse_args()

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)

    is_valid = validate_market_data(data)
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
