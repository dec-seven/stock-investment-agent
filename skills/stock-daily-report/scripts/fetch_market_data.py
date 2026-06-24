#!/usr/bin/env python3
"""
收盘日报数据获取脚本
用法: python3 fetch_market_data.py [--date 2026-06-12] [--output /tmp/market_data.json]

数据源优先级:
- 国内数据: AKShare 优先 → 失败标记 need_websearch（由 AI Agent 用 WebSearch 补充）
- 国外数据: yfinance 优先 → 失败标记 need_websearch（由 AI Agent 用 WebSearch 补充）

核心前提: 数据务必准确。获取不到的数据标记 need_websearch，不要返回假数据。
"""
import json
import sys
import os
import argparse
import time
import traceback
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'shared'))
from utils import safe_float

# ==================== 数据源导入 ====================

# AkShare - A股数据（国内数据优先源）
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    print("[WARN] AkShare 未安装，A股数据将标记 need_websearch", file=sys.stderr)

# yfinance - 海外数据（国外数据优先源）
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("[WARN] yfinance 未安装，海外数据将标记 need_websearch", file=sys.stderr)


# ==================== 工具函数 ====================

def validate_number(val, field_name=""):
    """校验数字是否有效（非零、非空）"""
    if val is None or val == 0 or val == 0.0:
        return False
    return True


def retry(func, max_retries=2, delay=1.0, description=""):
    """带重试的函数调用"""
    for attempt in range(max_retries):
        try:
            result = func()
            return result
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[WARN] {description} 第{attempt+1}次失败: {str(e)[:60]}，{delay}s后重试", file=sys.stderr)
                time.sleep(delay)
            else:
                print(f"[ERROR] {description} 重试{max_retries}次均失败: {str(e)[:80]}", file=sys.stderr)
    return None


# ==================== 国内数据（AKShare 优先） ====================

# AkShare 指数代码映射
INDEX_MAP = {
    "上证指数": ("000001", "sh"),
    "深证成指": ("399001", "sz"),
    "创业板指": ("399006", "sz"),
    "科创50":   ("000688", "sh"),
    "北证50":   ("899050", "bj"),
    "沪深300":  ("000300", "sh"),
    "上证50":   ("000016", "sh"),
}


def get_indices_akshare():
    """A股主要指数 - 通过 AkShare 获取"""
    result = []

    if not AKSHARE_AVAILABLE:
        print("[WARN] AkShare 不可用，A股指数标记 need_websearch", file=sys.stderr)
        return None

    success_count = 0
    for name, (code, prefix) in INDEX_MAP.items():
        try:
            symbol = f"{prefix}{code}"
            df = ak.stock_zh_index_daily(symbol=symbol)
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                prev_close = safe_float(df.iloc[-2].get("close", 0)) if len(df) >= 2 else 0
                close = safe_float(latest.get("close", 0))
                pct = round((close - prev_close) / prev_close * 100, 2) if prev_close else 0
                high = safe_float(latest.get("high", close))
                low = safe_float(latest.get("low", close))
                open_price = safe_float(latest.get("open", close))
                change = round(close - prev_close, 2)
                amplitude = round((high - low) / prev_close * 100, 2) if prev_close else 0

                if validate_number(close, name):
                    result.append({
                        "code": code,
                        "name": name,
                        "close": round(close, 2),
                        "pct": pct,
                        "change": change,
                        "high": round(high, 2),
                        "low": round(low, 2),
                        "open": round(open_price, 2),
                        "prev_close": round(prev_close, 2),
                        "amplitude": amplitude,
                        "source": "akshare",
                    })
                    success_count += 1
                    print(f"[OK] AkShare {name}: {close:.2f} ({pct:+.2f}%)", file=sys.stderr)
                else:
                    result.append({"name": name, "error": "数据无效(收盘价为0)", "need_websearch": True})
            else:
                result.append({"name": name, "error": "AkShare返回空", "need_websearch": True})
        except Exception as e:
            result.append({"name": name, "error": str(e)[:60], "need_websearch": True})
            print(f"[WARN] AkShare {name} 失败: {str(e)[:60]}", file=sys.stderr)

    if success_count < 3:
        print(f"[WARN] AkShare 仅获取 {success_count}/{len(INDEX_MAP)} 个指数，标记全部 need_websearch", file=sys.stderr)
        return None

    # 补齐缺失的指数
    result_names = {r.get("name") for r in result if "error" not in r}
    existing_error_names = {r.get("name") for r in result if "error" in r}
    for name, (code, prefix) in INDEX_MAP.items():
        if name not in result_names and name not in existing_error_names:
            result.append({"name": name, "error": "获取失败", "need_websearch": True})

    return result


def get_indices():
    """A股主要指数 - AkShare 优先"""
    result = retry(get_indices_akshare, max_retries=2, delay=2.0, description="A股指数获取")

    if result is None:
        default_indices = list(INDEX_MAP.keys())
        result = [{"name": name, "error": "AkShare不可用", "need_websearch": True} for name in default_indices]

    return result


def get_market_breadth_akshare():
    """涨跌家数 + 涨停池 - 通过 AkShare 获取（多接口尝试）"""
    if not AKSHARE_AVAILABLE:
        return None

    result = {"up_count": 0, "down_count": 0, "flat_count": 0,
              "limit_up_count": 0, "limit_down_count": 0,
              "limit_up_list": [], "limit_down_list": []}

    # 方式1: stock_zh_a_spot_em (东方财富实时行情)
    try:
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            up_count = 0
            down_count = 0
            flat_count = 0
            limit_up = 0
            limit_down = 0

            for _, row in df.iterrows():
                pct = safe_float(row.get("涨跌幅", 0))
                if pct > 0:
                    up_count += 1
                elif pct < 0:
                    down_count += 1
                else:
                    flat_count += 1

                if pct >= 9.9:
                    limit_up += 1
                elif pct <= -9.9:
                    limit_down += 1

            result["up_count"] = up_count
            result["down_count"] = down_count
            result["flat_count"] = flat_count
            result["limit_up_count"] = limit_up
            result["limit_down_count"] = limit_down
            result["source"] = "akshare"
            print(f"[OK] AkShare 涨跌家数: 上涨{up_count} 下跌{down_count} 涨停{limit_up} 跌停{limit_down}", file=sys.stderr)
        else:
            return None
    except Exception as e:
        print(f"[WARN] AkShare stock_zh_a_spot_em 获取涨跌家数失败: {str(e)[:60]}", file=sys.stderr)
        return None

    # 涨停池（可选补充）
    try:
        today = datetime.now().strftime("%Y%m%d")
        df_zt = ak.stock_zt_pool_em(date=today)
        if df_zt is not None and not df_zt.empty:
            result["limit_up_count"] = len(df_zt)
            for _, row in df_zt.head(15).iterrows():
                result["limit_up_list"].append({
                    "code": str(row.get("代码", "")),
                    "name": str(row.get("名称", "")),
                    "pct": safe_float(row.get("涨跌幅", 0)),
                    "reason": str(row.get("所属行业", "")),
                })
            print(f"[OK] AkShare 涨停池: {len(df_zt)} 只", file=sys.stderr)
    except Exception as e:
        print(f"[WARN] AkShare 涨停池获取失败: {str(e)[:60]}", file=sys.stderr)

    return result


def get_market_breadth():
    """涨跌家数 + 涨停池 - AkShare 优先"""
    result = retry(get_market_breadth_akshare, max_retries=2, delay=2.0, description="涨跌家数获取")

    if result is None:
        result = {"up_count": 0, "down_count": 0, "flat_count": 0,
                  "limit_up_count": 0, "limit_down_count": 0,
                  "limit_up_list": [], "limit_down_list": [],
                  "error": "AkShare不可用", "need_websearch": True}

    return result


def get_sectors_akshare():
    """申万一级行业涨跌 + 资金流向 - 通过 AkShare 获取（多接口尝试）"""
    if not AKSHARE_AVAILABLE:
        return None

    # 方式1: stock_board_industry_name_em (东方财富行业板块)
    try:
        df = ak.stock_board_industry_name_em()
        if df is not None and not df.empty:
            result = []
            for _, row in df.iterrows():
                pct = safe_float(row.get("涨跌幅", 0))
                main_net = safe_float(row.get("主力净流入-净额", 0)) if "主力净流入-净额" in df.columns else 0
                main_pct = safe_float(row.get("主力净流入-净占比", 0)) if "主力净流入-净占比" in df.columns else 0
                result.append({
                    "name": str(row.get("板块名称", "")),
                    "code": str(row.get("板块代码", "")),
                    "pct": pct,
                    "main_net": main_net,
                    "main_pct": main_pct,
                })
            result.sort(key=lambda x: x["pct"], reverse=True)
            print(f"[OK] AkShare 行业板块: 获取 {len(result)} 个板块", file=sys.stderr)
            return result
    except Exception as e:
        print(f"[WARN] AkShare stock_board_industry_name_em 失败: {str(e)[:60]}", file=sys.stderr)

    # 方式2: stock_sector_spot (同花顺行业板块)
    try:
        df = ak.stock_sector_spot(indicator="行业资金流")
        if df is not None and not df.empty:
            result = []
            for _, row in df.iterrows():
                name = str(row.get("名称", row.get("行业", "")))
                pct = safe_float(row.get("涨跌幅", row.get("涨幅", 0)))
                main_net = safe_float(row.get("主力净流入", 0)) if "主力净流入" in df.columns else 0
                if name:
                    result.append({"name": name, "code": "", "pct": pct, "main_net": main_net, "main_pct": 0})
            result.sort(key=lambda x: x["pct"], reverse=True)
            if result:
                print(f"[OK] AkShare(同花顺) 行业板块: 获取 {len(result)} 个板块", file=sys.stderr)
                return result
    except Exception as e:
        print(f"[WARN] AkShare stock_sector_spot 失败: {str(e)[:60]}", file=sys.stderr)

    return None


def get_sectors():
    """申万一级行业涨跌 - AkShare 优先"""
    result = retry(get_sectors_akshare, max_retries=2, delay=2.0, description="行业板块获取")

    if result is None:
        result = [{"error": "AkShare不可用", "need_websearch": True}]

    return result


def get_concepts_akshare():
    """概念板块涨跌 TOP - 通过 AkShare 获取"""
    if not AKSHARE_AVAILABLE:
        return None

    try:
        df = ak.stock_board_concept_name_em()
        if df is not None and not df.empty:
            sorted_df = df.sort_values("涨跌幅", ascending=False)
            result = {"top": [], "bottom": []}
            for _, row in sorted_df.head(10).iterrows():
                result["top"].append({
                    "name": str(row.get("板块名称", "")),
                    "pct": safe_float(row.get("涨跌幅", 0)),
                })
            for _, row in sorted_df.tail(10).iterrows():
                result["bottom"].append({
                    "name": str(row.get("板块名称", "")),
                    "pct": safe_float(row.get("涨跌幅", 0)),
                })
            print(f"[OK] AkShare 概念板块: TOP10 + BOTTOM10", file=sys.stderr)
            return result
    except Exception as e:
        print(f"[WARN] AkShare 概念板块失败: {str(e)[:60]}", file=sys.stderr)

    return None


def get_concepts():
    """概念板块涨跌 TOP - AkShare 优先"""
    result = retry(get_concepts_akshare, max_retries=2, delay=2.0, description="概念板块获取")

    if result is None:
        result = {"top": [], "bottom": [], "error": "AkShare不可用", "need_websearch": True}

    return result


def get_north_bound_akshare():
    """北向资金 - 通过 AkShare 获取（多接口尝试）"""
    if not AKSHARE_AVAILABLE:
        return None

    # 方式1: stock_hsgt_hist_em (东方财富北向资金)
    try:
        df = ak.stock_hsgt_hist_em(symbol="北向资金")
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            net_col = None
            for col in df.columns:
                if "净流入" in str(col) or "北向" in str(col):
                    net_col = col
                    break
            if net_col:
                result = {
                    "latest": {
                        "date": str(latest.get("日期", "")),
                        "net_amount": safe_float(latest.get(net_col, 0)),
                    },
                    "daily_records": [],
                    "source": "akshare",
                }
                for _, row in df.tail(5).iterrows():
                    result["daily_records"].append({
                        "date": str(row.get("日期", "")),
                        "net_amount": safe_float(row.get(net_col, 0)),
                    })
                print(f"[OK] AkShare 北向资金: {result['latest']['net_amount']:.2f}亿", file=sys.stderr)
                return result
    except Exception as e:
        print(f"[WARN] AkShare stock_hsgt_hist_em 获取北向资金失败: {str(e)[:60]}", file=sys.stderr)

    return None


def get_north_bound():
    """北向资金 - AkShare 优先"""
    result = retry(get_north_bound_akshare, max_retries=2, delay=2.0, description="北向资金获取")

    if result is None:
        result = {"latest": {}, "daily_records": [], "error": "AkShare不可用", "need_websearch": True}

    return result


def get_dragon_tiger_akshare(date_str):
    """龙虎榜 - 通过 AkShare 获取"""
    if not AKSHARE_AVAILABLE:
        return None

    try:
        df = ak.stock_lhb_detail_em(start_date=date_str, end_date=date_str)
        if df is not None and not df.empty:
            result = []
            for _, row in df.head(20).iterrows():
                result.append({
                    "code": str(row.get("代码", "")),
                    "name": str(row.get("名称", "")),
                    "pct": safe_float(row.get("涨跌幅", 0)),
                    "reason": str(row.get("上榜原因", "")),
                    "buy_amount": safe_float(row.get("买入额", 0)) if "买入额" in df.columns else 0,
                    "sell_amount": safe_float(row.get("卖出额", 0)) if "卖出额" in df.columns else 0,
                    "net_amount": safe_float(row.get("净额", 0)) if "净额" in df.columns else 0,
                })
            print(f"[OK] AkShare 龙虎榜: {len(result)} 条记录", file=sys.stderr)
            return result
    except Exception as e:
        print(f"[WARN] AkShare 龙虎榜失败: {str(e)[:60]}", file=sys.stderr)

    return None


def get_dragon_tiger(date_str):
    """龙虎榜 - AkShare 优先"""
    result = retry(lambda: get_dragon_tiger_akshare(date_str), max_retries=2, delay=2.0, description="龙虎榜获取")

    if result is None:
        result = [{"error": "AkShare不可用", "need_websearch": True}]

    return result


def get_margin_trading_akshare():
    """融资融券余额 - 通过 AkShare 获取"""
    if not AKSHARE_AVAILABLE:
        return None

    try:
        today = datetime.now().strftime("%Y%m%d")
        df = ak.stock_margin_sse(start_date=today, end_date=today)
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            result = {
                "total_balance": safe_float(latest.get("融资融券余额", 0)) if "融资融券余额" in df.columns else 0,
                "fin_balance": safe_float(latest.get("融资余额", 0)) if "融资余额" in df.columns else 0,
                "margin_balance": safe_float(latest.get("融券余额", 0)) if "融券余额" in df.columns else 0,
                "source": "akshare",
            }
            print(f"[OK] AkShare 两融余额: {result['total_balance']:.2f}亿", file=sys.stderr)
            return result
    except Exception as e:
        print(f"[WARN] AkShare 两融余额失败: {str(e)[:60]}", file=sys.stderr)

    return None


def get_margin_trading():
    """融资融券余额 - AkShare 优先"""
    result = retry(get_margin_trading_akshare, max_retries=2, delay=2.0, description="两融余额获取")

    if result is None:
        result = {"error": "AkShare不可用", "need_websearch": True}

    return result


def get_turnover_akshare():
    """两市成交额 - 通过 AkShare 获取"""
    if not AKSHARE_AVAILABLE:
        return None

    try:
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            amount_col = None
            for col in df.columns:
                if "成交额" in str(col):
                    amount_col = col
                    break
            if amount_col:
                total = df[amount_col].sum()
                total_yi = round(total / 1e8, 2)
                result = {"total": total_yi, "source": "akshare"}
                print(f"[OK] AkShare 两市成交额: {total_yi:.2f}亿", file=sys.stderr)
                return result
    except Exception as e:
        print(f"[WARN] AkShare stock_zh_a_spot_em 获取成交额失败: {str(e)[:60]}", file=sys.stderr)

    # 回退到指数成交额
    try:
        sh_df = ak.stock_zh_index_daily(symbol="sh000001")
        sz_df = ak.stock_zh_index_daily(symbol="sz399001")
        if sh_df is not None and not sh_df.empty and sz_df is not None and not sz_df.empty:
            sh_amount = 0
            sz_amount = 0
            for col in sh_df.columns:
                if "成交额" in str(col) or "amount" in str(col).lower():
                    sh_amount = safe_float(sh_df.iloc[-1].get(col, 0))
                    break
            for col in sz_df.columns:
                if "成交额" in str(col) or "amount" in str(col).lower():
                    sz_amount = safe_float(sz_df.iloc[-1].get(col, 0))
                    break

            total_yi = round((sh_amount + sz_amount) / 1e8, 2) if (sh_amount + sz_amount) > 0 else 0
            if total_yi > 0:
                result = {"total": total_yi, "source": "akshare-index"}
                print(f"[OK] AkShare(index) 两市成交额: {total_yi:.2f}亿", file=sys.stderr)
                return result
    except Exception as e:
        print(f"[WARN] AkShare stock_zh_index_daily 获取成交额失败: {str(e)[:60]}", file=sys.stderr)

    return None


def get_turnover():
    """两市成交额 - AkShare 优先"""
    result = retry(get_turnover_akshare, max_retries=2, delay=2.0, description="成交额获取")

    if result is None:
        result = {"total": 0, "error": "AkShare不可用", "need_websearch": True}

    return result


# ==================== 主函数 ====================

def main():
    parser = argparse.ArgumentParser(description="收盘日报数据获取脚本")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="交易日期")
    parser.add_argument("--output", default=None, help="输出文件路径（默认 stdout）")
    args = parser.parse_args()

    trade_date = args.date.replace("-", "")

    print(f"[INFO] 开始获取数据，交易日期: {args.date}", file=sys.stderr)
    print(f"[INFO] AkShare: {'可用' if AKSHARE_AVAILABLE else '不可用'}", file=sys.stderr)

    # === 获取国内数据（AkShare 优先） ===
    print("\n[INFO] === 获取国内数据（AkShare 优先） ===", file=sys.stderr)
    indices = get_indices()
    market_breadth = get_market_breadth()
    sectors = get_sectors()
    concepts = get_concepts()
    north_bound = get_north_bound()
    dragon_tiger = get_dragon_tiger(trade_date)
    margin_trading = get_margin_trading()
    turnover = get_turnover()

    # 构建输出数据
    data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "trade_date": args.date,
        "indices": indices,
        "market_breadth": market_breadth,
        "sectors": sectors,
        "concepts": concepts,
        "north_bound": north_bound,
        "dragon_tiger": dragon_tiger,
        "margin_trading": margin_trading,
        "turnover": turnover,
    }

    # === 统计需要 WebSearch 补充的数据 ===
    need_websearch = []

    # 检查指数
    for idx in indices:
        if idx.get("need_websearch") and idx.get("name") not in {n for n in need_websearch}:
            need_websearch.append(f"国内:{idx.get('name', '未知指数')}")

    # 检查涨跌家数
    if market_breadth.get("need_websearch"):
        need_websearch.append("国内:涨跌家数")

    # 检查行业板块
    if sectors and isinstance(sectors, list) and sectors[0].get("need_websearch"):
        need_websearch.append("国内:行业板块")

    # 检查概念板块
    if concepts.get("need_websearch"):
        need_websearch.append("国内:概念板块")

    # 检查北向资金
    if north_bound.get("need_websearch"):
        need_websearch.append("国内:北向资金")

    # 检查龙虎榜
    if dragon_tiger and isinstance(dragon_tiger, list) and dragon_tiger[0].get("need_websearch"):
        need_websearch.append("国内:龙虎榜")

    # 检查两融
    if margin_trading.get("need_websearch"):
        need_websearch.append("国内:两融余额")

    # 检查成交额
    if turnover.get("need_websearch"):
        need_websearch.append("国内:成交额")

    if need_websearch:
        print(f"\n[INFO] === 需要使用 WebSearch 补充 ({len(need_websearch)} 项) ===", file=sys.stderr)
        for item in need_websearch:
            print(f"  - {item}", file=sys.stderr)
        print(f"\n[INFO] AI Agent 应使用 WebSearch 工具获取以上数据，并更新 market_data.json", file=sys.stderr)
    else:
        print(f"\n[OK] 所有数据获取成功，无需 WebSearch 补充", file=sys.stderr)

    # 数据质量报告
    total_fields = len(indices) + 7  # indices + 7个独立模块
    success_fields = sum(1 for idx in indices if "error" not in idx and not idx.get("need_websearch"))
    if not market_breadth.get("need_websearch"):
        success_fields += 1
    if sectors and not sectors[0].get("need_websearch"):
        success_fields += 1
    if not concepts.get("need_websearch"):
        success_fields += 1
    if not north_bound.get("need_websearch"):
        success_fields += 1
    if dragon_tiger and not dragon_tiger[0].get("need_websearch"):
        success_fields += 1
    if not margin_trading.get("need_websearch"):
        success_fields += 1
    if not turnover.get("need_websearch"):
        success_fields += 1

    print(f"\n[INFO] 数据质量: {success_fields}/{total_fields} 字段成功获取 ({success_fields/total_fields*100:.0f}%)", file=sys.stderr)

    # 输出
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"\n[OK] 数据已保存到: {args.output}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
