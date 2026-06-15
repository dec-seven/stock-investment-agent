#!/usr/bin/env python3
"""
共享数据获取模块 - 供 stock-morning-brief 和 stock-daily-report 共用

数据源优先级:
- 国内数据: AKShare 优先 → 失败标记 need_websearch
- 国外数据: yfinance 优先 → 失败标记 need_websearch

用法:
    from shared.data_fetcher import get_a_indices, get_market_breadth, get_us_data, ...

核心前提: 数据务必准确。获取不到的数据标记 need_websearch，不要返回假数据。
"""
import sys
import time
from datetime import datetime, timedelta

# 引用共享工具函数
from shared.utils import safe_float, validate_number, retry

# ==================== 数据源导入 ====================

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    print("[WARN] AkShare 未安装，A股数据将标记 need_websearch", file=sys.stderr)

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("[WARN] yfinance 未安装，海外数据将标记 need_websearch", file=sys.stderr)


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


def get_a_indices_akshare():
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


def get_a_indices():
    """A股主要指数 - AkShare 优先"""
    result = retry(get_a_indices_akshare, max_retries=2, delay=2.0, description="A股指数获取")

    if result is None:
        default_indices = list(INDEX_MAP.keys())
        result = [{"name": name, "error": "AkShare不可用", "need_websearch": True} for name in default_indices]

    return result


def get_market_breadth_akshare():
    """涨跌家数 - 通过 AkShare 获取（多接口尝试）"""
    if not AKSHARE_AVAILABLE:
        return None

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

            result = {
                "up_count": up_count,
                "down_count": down_count,
                "flat_count": flat_count,
                "limit_up": limit_up,
                "limit_down": limit_down,
                "source": "akshare",
            }
            print(f"[OK] AkShare 涨跌家数: 上涨{up_count} 下跌{down_count} 涨停{limit_up} 跌停{limit_down}", file=sys.stderr)
            return result
    except Exception as e:
        print(f"[WARN] AkShare stock_zh_a_spot_em 获取涨跌家数失败: {str(e)[:60]}", file=sys.stderr)

    # 方式2: stock_market_activity_legu (乐股网市场活跃度)
    try:
        df = ak.stock_market_activity_legu()
        if df is not None and not df.empty:
            latest = df.iloc[-1] if len(df) > 0 else None
            if latest is not None:
                up_count = safe_float(latest.get("上涨家数", 0), 0)
                down_count = safe_float(latest.get("下跌家数", 0), 0)
                flat_count = safe_float(latest.get("平盘家数", 0), 0)
                limit_up = safe_float(latest.get("涨停家数", 0), 0)
                limit_down = safe_float(latest.get("跌停家数", 0), 0)

                if up_count > 0 or down_count > 0:
                    result = {
                        "up_count": int(up_count),
                        "down_count": int(down_count),
                        "flat_count": int(flat_count),
                        "limit_up": int(limit_up),
                        "limit_down": int(limit_down),
                        "source": "akshare-legu",
                    }
                    print(f"[OK] AkShare(legu) 涨跌家数: 上涨{int(up_count)} 下跌{int(down_count)}", file=sys.stderr)
                    return result
    except Exception as e:
        print(f"[WARN] AkShare stock_market_activity_legu 获取涨跌家数失败: {str(e)[:60]}", file=sys.stderr)

    return None


def get_market_breadth():
    """涨跌家数 - AkShare 优先"""
    result = retry(get_market_breadth_akshare, max_retries=2, delay=2.0, description="涨跌家数获取")

    if result is None:
        result = {"up_count": 0, "down_count": 0, "flat_count": 0, "limit_up": 0, "limit_down": 0,
                  "error": "AkShare不可用", "need_websearch": True}

    return result


def get_sectors_akshare():
    """申万一级行业涨跌 - 通过 AkShare 获取（多接口尝试）"""
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
                result.append({
                    "name": str(row.get("板块名称", "")),
                    "code": str(row.get("板块代码", "")),
                    "pct": pct,
                    "main_net": main_net,
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
                if name:
                    result.append({"name": name, "code": "", "pct": pct, "main_net": 0})
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


def get_north_bound_akshare():
    """北向资金 - 通过 AkShare 获取（多接口尝试）"""
    if not AKSHARE_AVAILABLE:
        return None

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
        print(f"[WARN] AkShare 获取北向资金失败: {str(e)[:60]}", file=sys.stderr)

    return None


def get_north_bound():
    """北向资金 - AkShare 优先"""
    result = retry(get_north_bound_akshare, max_retries=2, delay=2.0, description="北向资金获取")

    if result is None:
        result = {"latest": {}, "daily_records": [], "error": "AkShare不可用", "need_websearch": True}

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
        print(f"[WARN] AkShare 获取成交额失败: {str(e)[:60]}", file=sys.stderr)

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


# ==================== 国外数据（yfinance 优先） ====================

# yfinance Ticker 映射
YF_TICKERS = {
    # 美股指数
    "dow":    {"symbol": "^DJI",  "name": "道琼斯"},
    "sp500":  {"symbol": "^GSPC", "name": "标普500"},
    "nasdaq": {"symbol": "^IXIC", "name": "纳斯达克"},
    "vix":    {"symbol": "^VIX",  "name": "VIX恐慌指数"},
    "sox":    {"symbol": "^SOX",  "name": "费城半导体"},
    # 美股个股
    "nvda":   {"symbol": "NVDA",  "name": "英伟达"},
    "tsla":   {"symbol": "TSLA",  "name": "特斯拉"},
    # 大宗商品期货
    "oil":    {"symbol": "CL=F",  "name": "WTI原油"},
    "gold":   {"symbol": "GC=F",  "name": "COMEX黄金"},
    # 全球指数
    "nikkei": {"symbol": "^N225", "name": "日经225"},
    "hsi":    {"symbol": "^HSI",  "name": "恒生指数"},
    # 汇率
    "dxy":    {"symbol": "DX-Y.NYB", "name": "美元指数"},
    "cnh":    {"symbol": "CNY=X",     "name": "离岸人民币"},
}


def get_yfinance_single(key, info):
    """通过 yfinance 获取单个品种数据"""
    if not YFINANCE_AVAILABLE:
        return None

    try:
        ticker = yf.Ticker(info["symbol"])
        hist = ticker.history(period='2d')
        if hist is not None and len(hist) >= 2:
            latest = hist.iloc[-1]
            prev = hist.iloc[-2]
            close = float(latest['Close'])
            prev_close = float(prev['Close'])
            pct = round((close - prev_close) / prev_close * 100, 2)
            high = float(latest.get('High', close))
            low = float(latest.get('Low', close))

            if validate_number(close, info["name"]):
                return {
                    "name": info["name"],
                    "close": round(close, 2),
                    "pct": pct,
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "source": "yfinance",
                }
    except Exception as e:
        err_str = str(e)
        if "Rate Limit" in err_str or "Too Many Requests" in err_str:
            print(f"[WARN] yfinance 限流，跳过 {info['name']}", file=sys.stderr)
        else:
            print(f"[WARN] yfinance {info['name']} 失败: {err_str[:50]}", file=sys.stderr)

    return None


def get_us_data():
    """美股数据 - yfinance 优先"""
    result = {}
    success_count = 0

    for key, info in YF_TICKERS.items():
        data = retry(
            lambda k=key, i=info: get_yfinance_single(k, i),
            max_retries=2, delay=1.5,
            description=f"yfinance {info['name']}"
        )
        if data is not None:
            result[key] = data
            success_count += 1
            print(f"[OK] yfinance {info['name']}: {data['close']:.2f} ({data['pct']:+.2f}%)", file=sys.stderr)
        else:
            result[key] = {"name": info["name"], "need_websearch": True}
            print(f"[WARN] yfinance {info['name']}: 标记 need_websearch", file=sys.stderr)

        # 请求间隔，避免限流
        time.sleep(0.5)

    print(f"[INFO] yfinance 成功获取 {success_count}/{len(YF_TICKERS)} 个品种", file=sys.stderr)
    return result


def get_global_markets():
    """全球市场数据 - 数据在 get_us_data() 中已包含"""
    return {"note": "全球市场数据已合并到 us_data 字段，通过 yfinance 获取"}


# ==================== 交易日历 ====================

def is_trade_date(date_str=None):
    """检查是否为交易日（通过 AkShare）"""
    if not AKSHARE_AVAILABLE:
        return None

    try:
        df = ak.tool_trade_date_hist_sina()
        if df is not None and not df.empty:
            trade_dates = set(df['trade_date'].astype(str).tolist())
            check_date = (date_str or datetime.now().strftime("%Y-%m-%d")).replace("-", "")
            return check_date in trade_dates
    except Exception as e:
        print(f"[WARN] AkShare 获取交易日历失败: {str(e)[:60]}", file=sys.stderr)

    return None


# ==================== 可用性检查 ====================

def check_availability():
    """检查数据源可用性"""
    return {
        "akshare": AKSHARE_AVAILABLE,
        "yfinance": YFINANCE_AVAILABLE,
    }
