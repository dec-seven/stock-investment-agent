#!/usr/bin/env python3
"""
股票入选跟踪器：维护每日早报入选股票及后续收益表现，并生成独立 HTML 表格。

用法：
  python3 stock_tracker.py update \
    --analysis ./tmp/llm_analysis.json \
    --date 2026-06-15 \
    --tracker ./data/stock_selection_tracker.json \
    --html ./tmp/stock_tracker.html

字段：入选日期、入选原因（10字以内）、入选时股价、次日/3日/5日/7日累计涨跌幅。
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_TRACKER = SKILL_DIR / "data" / "stock_selection_tracker.json"
DEFAULT_HTML = SKILL_DIR / "tmp" / "stock_tracker.html"
MAX_RECORDS = 50
RETURN_WINDOWS = [1, 3, 5, 7]


# ==================== 基础工具 ====================

def load_json(path, default):
    path = Path(path)
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def is_trade_elapsed(selected_date, current_date, days):
    """简化判断：当前日期距离入选日期达到 N 个自然日后才尝试补充。"""
    try:
        return (parse_date(current_date) - parse_date(selected_date)).days >= days
    except Exception:
        return False


def normalize_code(code):
    return str(code).strip().zfill(6)


def infer_market_prefix(code, market_class=""):
    code = normalize_code(code)
    market_class = (market_class or "").lower()
    if market_class in ("sh", "sz", "bj"):
        return market_class
    if code.startswith(("60", "68", "90")):
        return "sh"
    if code.startswith(("00", "30", "20")):
        return "sz"
    if code.startswith(("43", "83", "87", "92")):
        return "bj"
    return "sh"


def tencent_symbol(code, market_class=""):
    return f"{infer_market_prefix(code, market_class)}{normalize_code(code)}"


def safe_float(value, default=None):
    try:
        if value in (None, "", "-"):
            return default
        return float(value)
    except Exception:
        return default


def short_reason(stock):
    """从选股逻辑中压缩入选原因到10字以内。"""
    text = ""
    logic = stock.get("logic", {})
    if isinstance(logic, dict):
        text = logic.get("core") or logic.get("catalyst") or logic.get("data") or ""
    elif isinstance(logic, str):
        text = logic

    candidates = [
        ("有色", "有色涨价"),
        ("黄金", "黄金高位"),
        ("铜", "铜价上涨"),
        ("钼", "钼价上涨"),
        ("航天", "航天催化"),
        ("低空", "低空催化"),
        ("电池", "电池修复"),
        ("储能", "储能催化"),
        ("券商", "券商修复"),
        ("资金", "资金流入"),
        ("涨停", "涨停带动"),
        ("业绩", "业绩验证"),
        ("龙头", "行业龙头"),
    ]
    for key, reason in candidates:
        if key in text:
            return reason[:10]
    return "逻辑入选"


# ==================== 行情获取 ====================

def fetch_tencent_quote(code, market_class=""):
    """腾讯行情接口，返回当前价。"""
    if requests is None:
        return None
    symbol = tencent_symbol(code, market_class)
    url = f"http://qt.gtimg.cn/q={symbol}"
    try:
        resp = requests.get(url, timeout=10)
        resp.encoding = "gbk"
        match = re.search(r'="([^"]+)"', resp.text)
        if not match:
            return None
        parts = match.group(1).split("~")
        if len(parts) < 5:
            return None
        name = parts[1]
        close = safe_float(parts[3])
        prev_close = safe_float(parts[4])
        pct = safe_float(parts[32]) if len(parts) > 32 else None
        if close is None:
            return None
        return {
            "name": name,
            "code": normalize_code(code),
            "market_class": infer_market_prefix(code, market_class),
            "close": close,
            "prev_close": prev_close,
            "pct": pct,
            "source": "tencent",
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as exc:
        print(f"[WARN] 腾讯行情获取失败 {code}: {exc}", file=sys.stderr)
        return None


def fetch_price(code, market_class=""):
    quote = fetch_tencent_quote(code, market_class)
    if quote:
        return quote
    return {
        "name": "",
        "code": normalize_code(code),
        "market_class": infer_market_prefix(code, market_class),
        "close": None,
        "source": "unavailable",
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def calc_return(base_price, current_price):
    if base_price in (None, 0) or current_price is None:
        return None
    return round((current_price - base_price) / base_price * 100, 2)


# ==================== 维护逻辑 ====================

def ensure_tracker_shape(tracker):
    if not isinstance(tracker, dict):
        tracker = {}
    tracker.setdefault("version", "1.0")
    tracker.setdefault("updated_at", "")
    tracker.setdefault("max_records", MAX_RECORDS)
    tracker.setdefault("records", [])
    return tracker


def record_key(record):
    return (record.get("selected_date"), normalize_code(record.get("code", "")))


def add_selected_stocks(tracker, analysis_path, selected_date):
    analysis = load_json(analysis_path, {})
    stocks = analysis.get("STOCKS", [])
    if not isinstance(stocks, list):
        print("[WARN] analysis.STOCKS 不是数组，跳过新增", file=sys.stderr)
        return 0

    existing = {record_key(r) for r in tracker["records"]}
    added = 0

    for stock in stocks:
        code = normalize_code(stock.get("code", ""))
        if not code or code == "000000":
            continue
        key = (selected_date, code)
        if key in existing:
            continue
        market_class = stock.get("market_class", "")
        quote = fetch_price(code, market_class)
        selected_price = quote.get("close")
        record = {
            "selected_date": selected_date,
            "name": stock.get("name") or quote.get("name") or "",
            "code": code,
            "market_class": infer_market_prefix(code, market_class),
            "reason": short_reason(stock),
            "selected_price": selected_price,
            "selected_price_source": quote.get("source"),
            "selected_price_time": quote.get("fetched_at"),
            "returns": {
                "next_day": None,
                "day_3": None,
                "day_5": None,
                "day_7": None,
            },
            "return_prices": {
                "next_day": None,
                "day_3": None,
                "day_5": None,
                "day_7": None,
            },
            "last_checked_at": "",
        }
        tracker["records"].append(record)
        existing.add(key)
        added += 1

    return added


def update_returns(tracker, current_date):
    field_map = {
        1: "next_day",
        3: "day_3",
        5: "day_5",
        7: "day_7",
    }
    updated = 0

    for record in tracker["records"]:
        selected_price = record.get("selected_price")
        if selected_price in (None, 0):
            # 如果入选时价格缺失，尝试补一次，但不计算收益
            quote = fetch_price(record.get("code", ""), record.get("market_class", ""))
            if quote.get("close") is not None:
                record["selected_price"] = quote.get("close")
                record["selected_price_source"] = quote.get("source")
                record["selected_price_time"] = quote.get("fetched_at")
            continue

        returns = record.setdefault("returns", {})
        return_prices = record.setdefault("return_prices", {})
        needs_quote = False
        due_fields = []
        for days, field in field_map.items():
            if returns.get(field) is None and is_trade_elapsed(record.get("selected_date", ""), current_date, days):
                needs_quote = True
                due_fields.append(field)

        if not needs_quote:
            continue

        quote = fetch_price(record.get("code", ""), record.get("market_class", ""))
        current_price = quote.get("close")
        if current_price is None:
            continue
        pct = calc_return(record.get("selected_price"), current_price)
        for field in due_fields:
            returns[field] = pct
            return_prices[field] = current_price
            updated += 1
        record["last_checked_at"] = quote.get("fetched_at")

    return updated


def enforce_limit(tracker):
    max_records = int(tracker.get("max_records") or MAX_RECORDS)
    records = tracker.get("records", [])
    records.sort(key=lambda r: (r.get("selected_date", ""), r.get("code", "")))
    removed = max(0, len(records) - max_records)
    if removed:
        tracker["records"] = records[removed:]
    else:
        tracker["records"] = records
    return removed


def update_tracker(args):
    tracker = ensure_tracker_shape(load_json(args.tracker, {}))
    selected_date = args.date
    current_date = args.current_date or selected_date

    added = 0
    if args.analysis:
        added = add_selected_stocks(tracker, args.analysis, selected_date)

    updated = update_returns(tracker, current_date)
    removed = enforce_limit(tracker)
    tracker["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    save_json(args.tracker, tracker)
    if args.html:
        generate_html(tracker, args.html)

    print(json.dumps({
        "tracker": str(args.tracker),
        "html": str(args.html) if args.html else "",
        "added": added,
        "updated_returns": updated,
        "removed_old_records": removed,
        "total": len(tracker.get("records", [])),
    }, ensure_ascii=False))


# ==================== HTML 渲染 ====================

def pct_class(value):
    if value is None:
        return "neutral"
    return "up" if value >= 0 else "down"


def fmt_pct(value):
    if value is None:
        return "待补"
    return f"+{value:.2f}%" if value > 0 else f"{value:.2f}%"


def fmt_price(value):
    if value is None:
        return "待补"
    return f"{value:.2f}"


def render_rows(records):
    rows = []
    sorted_records = sorted(records, key=lambda r: (r.get("selected_date", ""), r.get("code", "")), reverse=True)
    for r in sorted_records:
        returns = r.get("returns", {}) or {}
        row = f"""
        <tr>
          <td>{r.get('selected_date', '')}</td>
          <td class="stock"><span>{r.get('name', '')}</span><em>{r.get('code', '')}</em></td>
          <td>{r.get('reason', '')}</td>
          <td class="num">{fmt_price(r.get('selected_price'))}</td>
          <td class="num {pct_class(returns.get('next_day'))}">{fmt_pct(returns.get('next_day'))}</td>
          <td class="num {pct_class(returns.get('day_3'))}">{fmt_pct(returns.get('day_3'))}</td>
          <td class="num {pct_class(returns.get('day_5'))}">{fmt_pct(returns.get('day_5'))}</td>
          <td class="num {pct_class(returns.get('day_7'))}">{fmt_pct(returns.get('day_7'))}</td>
        </tr>"""
        rows.append(row)
    if not rows:
        rows.append('<tr><td colspan="8" class="empty">暂无入选股票</td></tr>')
    return "\n".join(rows)


def generate_html(tracker, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = tracker.get("records", [])
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>早报入选股票跟踪</title>
  <style>
    :root {{
      --bg: #071426;
      --card: #0f2138;
      --card2: #132b49;
      --text: #edf4ff;
      --muted: #8ea4bf;
      --line: rgba(255,255,255,.1);
      --red: #ef4444;
      --green: #22c55e;
      --gold: #f5c542;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: radial-gradient(circle at top, #15365f 0, var(--bg) 42%); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .wrap {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 48px; }}
    .hero {{ display: flex; justify-content: space-between; gap: 20px; align-items: flex-end; margin-bottom: 22px; }}
    h1 {{ margin: 0; font-size: 30px; letter-spacing: .5px; }}
    .sub {{ color: var(--muted); margin-top: 8px; font-size: 14px; }}
    .badge {{ border: 1px solid rgba(245,197,66,.35); color: var(--gold); border-radius: 999px; padding: 8px 14px; background: rgba(245,197,66,.08); white-space: nowrap; }}
    .card {{ background: linear-gradient(180deg, rgba(19,43,73,.96), rgba(10,25,45,.96)); border: 1px solid var(--line); border-radius: 18px; overflow: hidden; box-shadow: 0 24px 80px rgba(0,0,0,.28); }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ text-align: left; color: #bfd2ea; font-weight: 700; font-size: 13px; padding: 15px 14px; background: rgba(255,255,255,.05); border-bottom: 1px solid var(--line); white-space: nowrap; }}
    td {{ padding: 14px; border-bottom: 1px solid var(--line); color: #e6eef9; font-size: 14px; }}
    tr:hover td {{ background: rgba(255,255,255,.035); }}
    .stock span {{ display: block; font-weight: 700; }}
    .stock em {{ display: block; color: var(--muted); font-style: normal; font-size: 12px; margin-top: 3px; }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .up {{ color: var(--red); font-weight: 700; }}
    .down {{ color: var(--green); font-weight: 700; }}
    .neutral {{ color: var(--muted); }}
    .empty {{ text-align: center; color: var(--muted); padding: 42px; }}
    .note {{ margin-top: 14px; color: var(--muted); font-size: 12px; line-height: 1.7; }}
    @media (max-width: 820px) {{
      .hero {{ display: block; }}
      .badge {{ display: inline-block; margin-top: 14px; }}
      .card {{ overflow-x: auto; }}
      table {{ min-width: 820px; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div>
        <h1>早报入选股票跟踪</h1>
        <div class="sub">跟踪每日早报入选标的的次日、3日、5日、7日累计涨跌幅。红涨绿跌，最多保留50只。</div>
      </div>
      <div class="badge">共 {len(records)} 只 · 更新于 {tracker.get('updated_at', '')}</div>
    </div>
    <div class="card">
      <table>
        <thead>
          <tr>
            <th>入选日期</th>
            <th>股票</th>
            <th>入选原因</th>
            <th class="num">入选时股价</th>
            <th class="num">次日累计涨跌幅</th>
            <th class="num">3日累计涨跌幅</th>
            <th class="num">5日累计涨跌幅</th>
            <th class="num">7日累计涨跌幅</th>
          </tr>
        </thead>
        <tbody>
          {render_rows(records)}
        </tbody>
      </table>
    </div>
    <div class="note">
      说明：累计涨跌幅以"入选时股价"为基准计算，反映从入选到各时间窗口的累计收益；后续窗口到期后自动补充。若行情接口暂不可用，则显示"待补"。本页仅用于复盘跟踪，不构成投资建议。
    </div>
  </div>
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")


def cmd_render(args):
    tracker = ensure_tracker_shape(load_json(args.tracker, {}))
    generate_html(tracker, args.html)
    print(json.dumps({"html": str(args.html), "total": len(tracker.get("records", []))}, ensure_ascii=False))


# ==================== 命令入口 ====================

def main():
    parser = argparse.ArgumentParser(description="早报入选股票跟踪器")
    sub = parser.add_subparsers(dest="command")

    p_update = sub.add_parser("update", help="新增当日入选股票并补充到期收益")
    p_update.add_argument("--analysis", help="llm_analysis.json 路径，用于新增当日入选股票")
    p_update.add_argument("--date", required=True, help="入选日期 YYYY-MM-DD")
    p_update.add_argument("--current-date", default=None, help="收益补充基准日期 YYYY-MM-DD，默认等于 --date")
    p_update.add_argument("--tracker", default=str(DEFAULT_TRACKER), help="跟踪JSON路径")
    p_update.add_argument("--html", default=str(DEFAULT_HTML), help="输出HTML路径")
    p_update.set_defaults(func=update_tracker)

    p_render = sub.add_parser("render", help="从现有JSON生成HTML")
    p_render.add_argument("--tracker", default=str(DEFAULT_TRACKER), help="跟踪JSON路径")
    p_render.add_argument("--html", default=str(DEFAULT_HTML), help="输出HTML路径")
    p_render.set_defaults(func=cmd_render)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
