#!/usr/bin/env python3
"""
AI 文本生成辅助脚本:读取 market_data.json → 自动推导规则字段 → 构建 LLM 提示词 → 解析 LLM 输出 → 生成 ai_texts.json

设计原则:
- 脚本管 FORMAT(HTML模板、评分条、卡片渲染)
- LLM 管 INSIGHT(市场定调、选股逻辑、风险解读)
- 规则推导自动化(情绪色彩、方向信号、区间估算)

用法:
  # Step 1: 准备 LLM 提示词 + 规则推导字段
  python3 generate_ai_texts.py prepare --data ./tmp/market_data.json --output-dir ./tmp/

  # Step 2: Agent 读取 analysis_prompt.md,完成分析后输出 llm_analysis.json

  # Step 3: 编译最终 ai_texts.json(合并规则字段 + LLM 分析 + HTML 模板)
  python3 generate_ai_texts.py compile --data ./tmp/market_data.json --analysis ./tmp/llm_analysis.json --output ./tmp/ai_texts.json
"""

import os
import sys
import json
import argparse

# 添加项目根目录到 sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 导入拆分后的模块
from shared.ai.prompt_builder import build_analysis_prompt
from shared.ai.compiler import compile_ai_texts
from shared.ai.response_parser import parse_llm_response, validate_llm_json
from shared.ai.html_builders import build_event_timeline_html
from shared.logger import get_logger

logger = get_logger('generate_ai_texts')


def cmd_prepare(args):
    """生成 LLM 分析提示词 + 规则推导字段"""
    try:
        data = json.load(open(args.data, encoding="utf-8"))
        logger.info(f"市场数据已加载", path=args.data)
    except FileNotFoundError:
        logger.error(f"文件不存在", path=args.data)
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"JSON格式错误", error=str(e))
        sys.exit(1)
    
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成 LLM 提示词(包含规则推导和数据摘要)
    prompt = build_analysis_prompt(data, output_dir)
    
    prompt_path = os.path.join(output_dir, "analysis_prompt.md")
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt)
    logger.info(f"LLM 分析提示词已保存", path=prompt_path)
    
    # 输出事件时间线 HTML(可从数据直接生成)
    events = data.get("news_events", {}).get("events", [])
    if events:
        event_html = build_event_timeline_html(events)
        event_path = os.path.join(output_dir, "event_timeline_auto.html")
        with open(event_path, "w", encoding="utf-8") as f:
            f.write(event_html)
        logger.info(f"事件时间线HTML已自动生成", path=event_path)
    
    print(f"\n[OK] 准备完成:")
    print(f"  - 规则推导字段: {output_dir}/ai_texts_rules.json")
    print(f"  - LLM提示词: {output_dir}/analysis_prompt.md")
    if events:
        print(f"  - 事件时间线: {output_dir}/event_timeline_auto.html")
    print(f"\n[INFO] 下一步: Agent 读取 {prompt_path},完成分析后输出 llm_analysis.json")
    print(f"[INFO] 然后运行: python3 generate_ai_texts.py compile --data {args.data} --analysis ./tmp/llm_analysis.json --output ./tmp/ai_texts.json")


def cmd_compile(args):
    """编译最终 ai_texts.json"""
    try:
        data = json.load(open(args.data, encoding="utf-8"))
        logger.info(f"市场数据已加载", path=args.data)
    except FileNotFoundError:
        logger.error(f"文件不存在", path=args.data)
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"JSON格式错误", error=str(e))
        sys.exit(1)
    
    try:
        analysis_text = open(args.analysis, encoding="utf-8").read()
        
        # 尝试解析 LLM 响应
        analysis = parse_llm_response(analysis_text)
        if analysis is None:
            # 尝试直接作为 JSON 解析
            try:
                analysis = json.load(open(args.analysis, encoding="utf-8"))
                logger.info(f"LLM 分析结果已加载(JSON格式)", path=args.analysis)
            except json.JSONDecodeError as e:
                logger.error(f"LLM 分析 JSON 格式错误", error=str(e))
                sys.exit(1)
        else:
            logger.info(f"LLM 分析结果已加载(文本解析)", path=args.analysis)
        
        # 验证 LLM 分析格式
        if not validate_llm_json(analysis):
            logger.warning("LLM 分析格式不完整,继续编译但可能缺少部分字段")
        
    except FileNotFoundError:
        logger.error(f"文件不存在", path=args.analysis)
        sys.exit(1)
    
    # 编译 ai_texts
    try:
        ai_texts = compile_ai_texts(data, analysis, args.output)
        logger.info(f"ai_texts.json 已生成", path=args.output)
        print(f"[OK] ai_texts.json 已保存: {args.output}")
    except Exception as e:
        logger.error(f"编译失败", error=str(e), exc_info=True)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="AI 文本生成辅助脚本")
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # prepare 命令
    prep_parser = subparsers.add_parser("prepare", help="生成 LLM 提示词 + 规则推导字段")
    prep_parser.add_argument("--data", required=True, help="market_data.json 路径")
    prep_parser.add_argument("--output-dir", default="./tmp/", help="输出目录")
    
    # compile 命令
    comp_parser = subparsers.add_parser("compile", help="编译最终 ai_texts.json")
    comp_parser.add_argument("--data", required=True, help="market_data.json 路径")
    comp_parser.add_argument("--analysis", required=True, help="LLM 分析结果 JSON 路径")
    comp_parser.add_argument("--output", required=True, help="输出 ai_texts.json 路径")
    
    args = parser.parse_args()
    
    if args.command == "prepare":
        cmd_prepare(args)
    elif args.command == "compile":
        cmd_compile(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
