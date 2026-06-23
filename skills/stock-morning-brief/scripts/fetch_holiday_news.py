#!/usr/bin/env python3
"""
节假日信息采集脚本 - 解决假期信息差问题
用法: python3 fetch_holiday_news.py --date 2026-06-23 --output ./tmp/holiday_news.json

作用：在节后首日（或任意交易日）自动搜集假期期间的关键产业链变化，
      输出结构化 JSON，供 generate_report.py / ai_texts 注入使用。

覆盖品类（可配置）：
  - 价格变化：存储/铜/油/黄金/锂/铁矿
  - 政策事件：美联储/央行/产业政策
  - 重大发布：英伟达/苹果/华为/国内大厂
  - AI/半导体/新能源行业动态
"""

import os, sys, json, argparse
from datetime import datetime, timedelta

# 屏蔽代理
for _k in ['http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY','all_proxy']:
    os.environ.pop(_k, None)

# ==================== 配置 ====================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(SCRIPT_DIR, "..", "data")
OUTPUT_DIR = os.path.join(DATA_DIR, "holiday_news")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 假期信息搜索关键词配置（节后首日权重1.5）
HOLIDAY_SEARCH_TOPICS = [
    {
        "category": "存储价格",
        "keywords": ["存储芯片 价格 涨价", "DRAM NAND 合约价 2026"],
        "why": "存储涨价是最常见的节假日信息差来源，Q3合约价通常在月中调整"
    },
    {
        "category": "铜价/高速铜缆",
        "keywords": ["铜价 LME 2026", "高速铜缆 算力"],
        "why": "铜缆算力方向，铜价波动影响成本和估值"
    },
    {
        "category": "AI重大发布",
        "keywords": ["英伟达 发布 2026", "OpenAI 发布 2026", "华为昇腾 2026"],
        "why": "假期期间AI大厂发布会常引发节后相关板块爆发"
    },
    {
        "category": "美联储/货币政策",
        "keywords": ["美联储 议息 利率 2026", "Fed rate 2026"],
        "why": "货币政策是科技股定价核心变量"
    },
    {
        "category": "能源/新能源",
        "keywords": ["原油 OPEC 2026", "电池 碳酸锂 价格 2026"],
        "why": "能源价格影响通胀预期；锂价影响新能源板块"
    },
    {
        "category": "国内产业政策",
        "keywords": ["半导体 政策 补贴 2026", "人工智能 产业政策 2026"],
        "why": "节假日期间政策文件可能发布，节后首日是最佳买点"
    }
]

# ==================== 数据获取 ====================

def get_commodity_prices():
    """
    用 AKShare 获取大宗商品最新价格（节前vs节后对比）
    返回 dict: {品种: {节前收盘, 最新价, 变化幅度}}
    """
    try:
        import akshare as ak
        import warnings
        warnings.filterwarnings('ignore')
    except ImportError:
        return {}

    results = {}

    # 黄金现货
    try:
        df = ak.spot_hist_sge(symbol='Au99.99')
        if df is not None and len(df) >= 2:
            last  = df.iloc[-1]
            prev  = df.iloc[-4] if len(df) >= 5 else df.iloc[0]
            chg   = round((float(last['close']) - float(prev['close'])) / float(prev['close']) * 100, 2)
            results['黄金'] = {
                'prev_close': float(prev['close']),
                'latest':     float(last['close']),
                'change_pct': chg,
                'date':       str(last.get('date', ''))
            }
    except Exception as e:
        print(f"  ⚠️ 黄金价格获取失败: {e}", file=sys.stderr)

    # 沪铜主力
    try:
        df = ak.futures_zh_daily_sina(symbol='CU0')
        if df is not None and len(df) >= 2:
            last  = df.iloc[-1]
            prev  = df.iloc[-4] if len(df) >= 5 else df.iloc[0]
            chg   = round((float(last['close']) - float(prev['close'])) / float(prev['close']) * 100, 2)
            results['沪铜'] = {
                'prev_close': float(prev['close']),
                'latest':     float(last['close']),
                'change_pct': chg,
                'date':       str(last.get('date', ''))
            }
    except Exception as e:
        print(f"  ⚠️ 铜价获取失败: {e}", file=sys.stderr)

    # 原油（SC主力）
    try:
        df = ak.futures_zh_daily_sina(symbol='SC0')
        if df is not None and len(df) >= 2:
            last  = df.iloc[-1]
            prev  = df.iloc[-4] if len(df) >= 5 else df.iloc[0]
            chg   = round((float(last['close']) - float(prev['close'])) / float(prev['close']) * 100, 2)
            results['原油SC'] = {
                'prev_close': float(prev['close']),
                'latest':     float(last['close']),
                'change_pct': chg,
                'date':       str(last.get('date', ''))
            }
    except Exception as e:
        print(f"  ⚠️ 原油SC价格获取失败: {e}", file=sys.stderr)

    # 碳酸锂（LC主力）
    try:
        df = ak.futures_zh_daily_sina(symbol='LC0')
        if df is not None and len(df) >= 2:
            last  = df.iloc[-1]
            prev  = df.iloc[-4] if len(df) >= 5 else df.iloc[0]
            chg   = round((float(last['close']) - float(prev['close'])) / float(prev['close']) * 100, 2)
            results['碳酸锂'] = {
                'prev_close': float(prev['close']),
                'latest':     float(last['close']),
                'change_pct': chg,
                'date':       str(last.get('date', ''))
            }
    except Exception as e:
        print(f"  ⚠️ 碳酸锂价格获取失败: {e}", file=sys.stderr)

    return results


def build_websearch_queries(date_str, holiday_start=None, holiday_end=None):
    """
    生成节假日信息搜索 Query 列表，供 Agent 用 WebSearch 搜索
    """
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    month    = date_obj.month
    day      = date_obj.day

    # 如果没有传节假日范围，默认往前推3个自然日
    if not holiday_start:
        holiday_start = (date_obj - timedelta(days=3)).strftime('%-m月%-d日')
    if not holiday_end:
        holiday_end   = (date_obj - timedelta(days=1)).strftime('%-m月%-d日')

    period_str = f"{holiday_start}至{holiday_end}"

    queries = []
    for topic in HOLIDAY_SEARCH_TOPICS:
        for kw in topic["keywords"]:
            queries.append({
                "query":    f"{kw} {month}月 假期期间",
                "category": topic["category"],
                "why":      topic["why"],
                "priority": "high"
            })

    # 追加综合性节后预判查询
    queries.append({
        "query":    f"A股 节后首日 {month}月{day}日 行业机会 预判",
        "category": "节后盘前综合",
        "why":      "综合判断节后首日资金方向",
        "priority": "high"
    })
    queries.append({
        "query":    f"存储芯片 DRAM 价格 涨价 {month}月",
        "category": "存储价格",
        "why":      "存储涨价对同有科技/兆易创新等节后催化",
        "priority": "high"
    })

    return queries


def generate_search_prompt(date_str, queries):
    """
    生成 Agent 用 WebSearch 时的提示词
    """
    lines = [
        f"## 节后首日信息差补全 — {date_str}",
        "",
        "以下是需要用 WebSearch 搜索的节假日期间关键变化，**必须全部搜索**：",
        ""
    ]
    for i, q in enumerate(queries, 1):
        lines.append(f"{i}. [{q['category']}] `{q['query']}`")
        lines.append(f"   — 为什么搜：{q['why']}")
        lines.append("")

    lines += [
        "---",
        "搜索完成后，将以下结果写入 holiday_news.json：",
        "- 找到的重要变化（价格变化/政策/发布会）",
        "- 对A股相关板块的影响判断",
        "- 节后首日强催化标志（若存在）",
        ""
    ]
    return "\n".join(lines)


# ==================== 主流程 ====================

def main():
    parser = argparse.ArgumentParser(description='节假日信息采集')
    parser.add_argument('--date',           default=datetime.now().strftime('%Y-%m-%d'))
    parser.add_argument('--holiday-start',  default=None, help='节假日开始，如 6月19日')
    parser.add_argument('--holiday-end',    default=None, help='节假日结束，如 6月21日')
    parser.add_argument('--output',         default=None)
    args = parser.parse_args()

    date_str   = args.date
    output_path = args.output or os.path.join(OUTPUT_DIR, f"{date_str}.json")

    print(f"\n🏖️  节假日信息采集 — {date_str}", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    # 1. 获取大宗商品节前→节后价格对比（AKShare）
    print("\n[STEP 1] 获取大宗商品价格变化...", file=sys.stderr)
    commodity_prices = get_commodity_prices()
    for name, data in commodity_prices.items():
        chg = data.get('change_pct', 0)
        direction = "↑" if chg > 0 else "↓"
        print(f"  {name}: {data.get('prev_close')} → {data.get('latest')} ({direction}{abs(chg):.1f}%)", file=sys.stderr)

    # 2. 生成 WebSearch 查询清单
    print("\n[STEP 2] 生成 WebSearch 查询清单...", file=sys.stderr)
    queries = build_websearch_queries(date_str, args.holiday_start, args.holiday_end)
    search_prompt = generate_search_prompt(date_str, queries)

    # 3. 写入结构化输出
    output = {
        "date":             date_str,
        "generated_at":     datetime.now().isoformat(),
        "commodity_prices": commodity_prices,
        "websearch_queries":queries,
        "search_prompt":    search_prompt,
        "holiday_findings": [],       # 由 Agent WebSearch 填充
        "sector_impact":    {},       # 由 Agent 填充：{板块: 影响判断}
        "strong_catalyst":  [],       # 由 Agent 填充：节后首日强催化股票
        "warning_signals":  []        # 解禁/政策负面等风险信号
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 输出: {output_path}", file=sys.stderr)
    print(f"   大宗商品价格: {len(commodity_prices)} 个品种", file=sys.stderr)
    print(f"   WebSearch 查询: {len(queries)} 条", file=sys.stderr)

    # 打印 WebSearch 提示词（供 Agent 用）
    print("\n" + "=" * 50, file=sys.stderr)
    print("📋 需要 Agent 用 WebSearch 搜索的内容：", file=sys.stderr)
    print(search_prompt, file=sys.stderr)

    print(output_path)  # stdout 只输出路径，供调用方捕获


if __name__ == '__main__':
    main()
