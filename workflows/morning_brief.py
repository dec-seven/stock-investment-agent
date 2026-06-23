"""
早报编排工作流：串联 4 个 Agent + 数据获取 + 编译 + 渲染 + 部署 + 推送。

状态机：
  fetch → macro → sector → stock → review → compile → render → deploy → push

特性：
- 断点续跑：state.json 记录进度，失败后从断点继续
- 双模式：
  - 在线（DEEPSEEK_API_KEY 存在）：4 Agent 并发调 LLM → 合并 llm_analysis.json
  - 离线（无 API Key）：复用现有 prepare → 等待外部执行 → compile（兼容人肉协议）
- 并发：在线模式下 macro/sector 可并行（stock/review 依赖前者）
- 失败回退：LLM 失败时 Agent 生成 prompt 片段，不阻断

用法：
  # 完整流程
  python3 -m workflows.morning_brief

  # 指定工作目录
  python3 -m workflows.morning_brief --work-dir /tmp/morning

  # 仅运行到某步骤（断点续跑）
  python3 -m workflows.morning_brief --from-step stock

  # 跳过部署/推送
  python3 -m workflows.morning_brief --skip-deploy --skip-push
"""

import os
import sys
import json
import time
import uuid
import argparse
import concurrent.futures
from datetime import datetime
from typing import Optional

# 项目根
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from agents.base import BaseAgent, AgentResult
from agents.macro_agent import MacroAgent
from agents.sector_agent import SectorAgent
from agents.stock_agent import StockAgent
from agents.review_agent import ReviewAgent
from agents.risk_manager_agent import RiskManagerAgent
from agents.learning_agent import LearningAgent
from shared.ai.llm_client import LLMClient
from shared.ai.tools import build_default_tools

# 默认工作目录
DEFAULT_WORK_DIR = os.path.join(PROJECT_ROOT, "skills", "stock-morning-brief", "tmp")

# 状态机步骤
STEPS = ["fetch", "macro", "sector", "stock", "risk_manager", "review", "compile", "render", "deploy", "push", "learn"]


class MorningBriefWorkflow:
    """早报编排工作流"""

    def __init__(self, work_dir: str = DEFAULT_WORK_DIR, llm_client: LLMClient = None):
        self.work_dir = work_dir
        os.makedirs(work_dir, exist_ok=True)

        self.llm = llm_client or LLMClient()
        self.tools = build_default_tools()

        # 文件路径
        self.market_data_path = os.path.join(work_dir, "market_data.json")
        self.llm_analysis_path = os.path.join(work_dir, "llm_analysis.json")
        self.ai_texts_path = os.path.join(work_dir, "ai_texts.json")
        self.html_path = os.path.join(work_dir, "morning_brief.html")
        self.state_path = os.path.join(work_dir, "workflow_state.json")

        # 运行 ID
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:4]

        # 5 个 Agent
        self.macro_agent = MacroAgent(llm_client=self.llm, tools=self.tools, run_id=self.run_id)
        self.sector_agent = SectorAgent(llm_client=self.llm, tools=self.tools, run_id=self.run_id)
        self.stock_agent = StockAgent(llm_client=self.llm, tools=self.tools, run_id=self.run_id)
        self.review_agent = ReviewAgent(llm_client=self.llm, tools=self.tools, run_id=self.run_id)
        self.risk_manager_agent = RiskManagerAgent(llm_client=self.llm, tools=self.tools, run_id=self.run_id)
        self.learning_agent = LearningAgent(llm_client=self.llm, tools=self.tools, run_id=self.run_id)

    def run(self, from_step: str = None, skip_deploy: bool = False, skip_push: bool = False) -> dict:
        """运行完整工作流。

        Args:
            from_step: 从指定步骤开始（断点续跑）
            skip_deploy: 跳过部署
            skip_push: 跳过推送
        """
        print(f"[Workflow] run_id={self.run_id}, LLM 模式={self.llm.mode}, work_dir={self.work_dir}")

        state = self._load_state()
        start_idx = STEPS.index(from_step) if from_step else 0
        results = {"run_id": self.run_id, "steps": {}, "mode": self.llm.mode}

        # 1. fetch: 获取市场数据
        if start_idx <= STEPS.index("fetch"):
            print("\n[1/9] 获取市场数据...")
            r = self.tools["fetch_data"].execute(output_path=self.market_data_path)
            results["steps"]["fetch"] = {"success": r.success, "error": r.error, "duration_ms": r.duration_ms}
            self._save_step("fetch", r.success)
            if not r.success:
                return self._fail(results, "fetch 失败", r.error)

        # 加载市场数据
        market_data = self._load_json(self.market_data_path)
        if not market_data:
            return self._fail(results, "market_data.json 加载失败")

        # 2-3. macro + sector: 在线模式可并行
        macro_result_data = state.get("macro_result", {})
        sector_result_data = state.get("sector_result", {})

        if self.llm.is_online() and start_idx <= STEPS.index("sector"):
            print("\n[2-3/9] 并行运行 macro + sector Agent...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                future_macro = executor.submit(
                    self.macro_agent.run,
                    {"market_data": market_data, "work_dir": self.work_dir}
                )
                future_sector = executor.submit(
                    self.sector_agent.run,
                    {"market_data": market_data, "work_dir": self.work_dir}
                )
                macro_res = future_macro.result()
                sector_res = future_sector.result()

            results["steps"]["macro"] = {"success": macro_res.success, "errors": macro_res.errors, "trace": macro_res.trace}
            results["steps"]["sector"] = {"success": sector_res.success, "errors": sector_res.errors, "trace": sector_res.trace}
            macro_result_data = macro_res.data
            sector_result_data = sector_res.data
            self._save_state({"macro_result": macro_result_data, "sector_result": sector_result_data})
        else:
            # 离线模式：串行
            if start_idx <= STEPS.index("macro"):
                print("\n[2/9] 运行 macro Agent...")
                macro_res = self.macro_agent.run({"market_data": market_data, "work_dir": self.work_dir})
                results["steps"]["macro"] = {"success": macro_res.success, "errors": macro_res.errors}
                macro_result_data = macro_res.data
                self._save_state({"macro_result": macro_result_data})

            if start_idx <= STEPS.index("sector"):
                print("\n[3/9] 运行 sector Agent...")
                sector_res = self.sector_agent.run({"market_data": market_data, "work_dir": self.work_dir})
                results["steps"]["sector"] = {"success": sector_res.success, "errors": sector_res.errors}
                sector_result_data = sector_res.data
                self._save_state({"sector_result": sector_result_data})

        # 4. stock: 选股（依赖 macro + sector）
        stock_result_data = state.get("stock_result", {})
        if start_idx <= STEPS.index("stock"):
            print("\n[4/9] 运行 stock Agent...")
            stock_res = self.stock_agent.run({
                "market_data": market_data,
                "macro_result": macro_result_data if isinstance(macro_result_data, dict) else {},
                "sector_result": sector_result_data if isinstance(sector_result_data, dict) else {},
                "work_dir": self.work_dir,
            })
            results["steps"]["stock"] = {"success": stock_res.success, "errors": stock_res.errors}
            stock_result_data = stock_res.data
            self._save_state({"stock_result": stock_result_data})

        # 5. risk_manager: 风控（依赖 stock）
        risk_manager_result_data = state.get("risk_manager_result", {})
        if start_idx <= STEPS.index("risk_manager"):
            print("\n[5/10] 运行 risk_manager Agent...")
            risk_res = self.risk_manager_agent.run({
                "market_data": market_data,
                "stock_result": stock_result_data if isinstance(stock_result_data, dict) else {},
                "work_dir": self.work_dir,
            })
            results["steps"]["risk_manager"] = {"success": risk_res.success, "errors": risk_res.errors}
            risk_manager_result_data = risk_res.data
            self._save_state({"risk_manager_result": risk_manager_result_data})

        # 6. review: 策略（依赖前面所有）
        review_result_data = state.get("review_result", {})
        if start_idx <= STEPS.index("review"):
            print("\n[6/10] 运行 review Agent...")
            review_res = self.review_agent.run({
                "market_data": market_data,
                "macro_result": macro_result_data if isinstance(macro_result_data, dict) else {},
                "sector_result": sector_result_data if isinstance(sector_result_data, dict) else {},
                "stock_result": stock_result_data if isinstance(stock_result_data, dict) else {},
                "work_dir": self.work_dir,
            })
            results["steps"]["review"] = {"success": review_res.success, "errors": review_res.errors}
            review_result_data = review_res.data
            self._save_state({"review_result": review_result_data})

        # 6. compile: 合并 Agent 输出 → llm_analysis.json + ai_texts.json
        if start_idx <= STEPS.index("compile"):
            print("\n[6/9] 编译 ai_texts.json...")
            compile_ok = self._compile(
                market_data, macro_result_data, sector_result_data,
                stock_result_data, review_result_data
            )
            results["steps"]["compile"] = {"success": compile_ok}
            self._save_step("compile", compile_ok)
            if not compile_ok:
                return self._fail(results, "compile 失败")

        # 7. render: 渲染 HTML
        if start_idx <= STEPS.index("render"):
            print("\n[7/9] 渲染 HTML 报告...")
            r = self.tools["render_report"].execute(
                data_path=self.market_data_path,
                ai_texts_path=self.ai_texts_path,
                html_path=self.html_path,
                analysis_json=self.llm_analysis_path,
            )
            results["steps"]["render"] = {"success": r.success, "error": r.error, "duration_ms": r.duration_ms}
            self._save_step("render", r.success)
            if not r.success:
                return self._fail(results, "render 失败", r.error)

        # 8. deploy
        cloudflare_url = ""
        if not skip_deploy and start_idx <= STEPS.index("deploy"):
            print("\n[8/9] 部署 Cloudflare...")
            r = self.tools["deploy_cloudflare"].execute(html_path=self.html_path)
            results["steps"]["deploy"] = {"success": r.success, "error": r.error, "data": r.data}
            self._save_step("deploy", r.success)
            if r.success and isinstance(r.data, dict):
                cloudflare_url = r.data.get("cloudflare_url", "")

        # 9. push
        if not skip_push and start_idx <= STEPS.index("push"):
            print("\n[9/10] 飞书推送...")
            r = self.tools["push_feishu"].execute(
                data_path=self.market_data_path,
                ai_texts_path=self.ai_texts_path,
                html_path=self.html_path,
                cloudflare_url=cloudflare_url,
            )
            results["steps"]["push"] = {"success": r.success, "error": r.error}
            self._save_step("push", r.success)

        # 10. learn: 学习本次报告中的方法论（可选）
        if start_idx <= STEPS.index("learn"):
            print("\n[10/10] 运行 Learning Agent...")
            # 读取 ai_texts.json 作为学习素材
            ai_texts = self._load_json(self.ai_texts_path)
            if ai_texts:
                # 提取关键分析内容（市场定位、板块方向、选股逻辑）
                learning_content = self._extract_learning_content(ai_texts, market_data)
                learn_res = self.learning_agent.run({
                    "source_type": "review",
                    "source_date": datetime.now().strftime("%Y-%m-%d"),
                    "source_title": f"早报自动复盘 {datetime.now().strftime('%Y-%m-%d')}",
                    "content": learning_content,
                    "force_update": False
                })
                results["steps"]["learn"] = {
                    "success": learn_res.success,
                    "summary": learn_res.data.get("summary", "") if learn_res.success else "",
                    "files_updated": learn_res.data.get("files_updated", []) if learn_res.success else []
                }
            else:
                results["steps"]["learn"] = {"success": False, "error": "ai_texts.json 不存在"}

        results["success"] = True
        results["cloudflare_url"] = cloudflare_url
        results["html_path"] = self.html_path
        print(f"\n[Workflow] 完成 ✓ run_id={self.run_id}")
        if cloudflare_url:
            print(f"[Workflow] Cloudflare URL: {cloudflare_url}")
        return results

    def _compile(self, market_data, macro, sector, stock, review) -> bool:
        """合并 4 个 Agent 输出为 llm_analysis.json，再调 compile 生成 ai_texts.json。

        在线模式：4 个 Agent 的 data 是字段字典，直接合并
        离线模式：4 个 Agent 生成 prompt 片段，复用现有 prepare → 等待外部执行
        """
        # 在线模式：合并字段
        if self.llm.is_online():
            merged = {}
            for agent_data in [macro, sector, stock, review]:
                if isinstance(agent_data, dict):
                    # 过滤掉非字段键（mode/prompt_path/fields）
                    for k, v in agent_data.items():
                        if k not in ("mode", "prompt_path", "fields"):
                            merged[k] = v

            if not merged:
                # 在线模式但没有合并到数据（LLM 全失败），回退到离线
                print("[Workflow] 在线模式 LLM 全失败，回退到离线 prepare...")
                return self._offline_compile()

            # 写入 llm_analysis.json
            with open(self.llm_analysis_path, "w", encoding="utf-8") as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)

            # 调 compile
            r = self.tools["compile_ai_texts"].execute(
                data_path=self.market_data_path,
                analysis_path=self.llm_analysis_path,
                output_path=self.ai_texts_path,
            )
            return r.success
        else:
            # 离线模式：复用现有 prepare（一次生成完整 prompt）
            return self._offline_compile()

    def _offline_compile(self) -> bool:
        """离线模式编译：复用现有 generate_ai_texts.py prepare。

        离线模式下：
        1. prepare 生成 analysis_prompt.md（完整 prompt）
        2. 等待外部执行 LLM → llm_analysis.json
        3. compile 生成 ai_texts.json

        本方法只执行 step 1，step 2 需外部完成，step 3 由用户再次运行 --from-step compile 触发。
        """
        print("[Workflow] 离线模式：生成 prompt，等待外部执行 LLM...")
        r = self.tools["prepare_prompt"].execute(
            data_path=self.market_data_path,
            output_dir=self.work_dir,
        )
        if r.success:
            print(f"[Workflow] prompt 已生成: {r.data.get('prompt_path', '')}")
            print("[Workflow] 请外部执行 LLM 生成 llm_analysis.json，然后运行:")
            print(f"  python3 -m workflows.morning_brief --from-step compile")
            return False  # 离线模式返回 False，等待外部执行
        return False

    def _load_json(self, path: str) -> dict:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _load_state(self) -> dict:
        return self._load_json(self.state_path)

    def _save_state(self, updates: dict):
        state = self._load_state()
        state.update(updates)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def _save_step(self, step: str, success: bool):
        self._save_state({f"step_{step}": {"success": success, "ts": datetime.now().isoformat()}})

    def _fail(self, results: dict, msg: str, detail: str = "") -> dict:
        results["success"] = False
        results["error"] = msg
        if detail:
            results["error_detail"] = detail
        print(f"[Workflow] 失败 ✗ {msg}: {detail}")
        return results

    def _extract_learning_content(self, ai_texts: dict, market_data: dict) -> str:
        """从 ai_texts 和 market_data 中提取可学习的分析内容"""
        parts = []

        # 1. 市场定位
        if "MARKET_TONE" in ai_texts:
            parts.append(f"【市场定位】\n{ai_texts['MARKET_TONE']}")

        if "DIRECTION_JUDGMENT" in ai_texts:
            parts.append(f"【方向判断】\n{ai_texts['DIRECTION_JUDGMENT']}")

        # 2. 板块方向
        if "SECTOR_DIRECTIONS" in ai_texts:
            parts.append(f"【板块方向】\n{ai_texts['SECTOR_DIRECTIONS']}")

        # 3. 选股逻辑
        if "STOCK_SELECTION" in ai_texts:
            # 提取文本，去除 HTML 标签
            import re
            text = re.sub(r'<[^>]+>', ' ', ai_texts['STOCK_SELECTION'])
            text = re.sub(r'\s+', ' ', text).strip()
            parts.append(f"【选股逻辑】\n{text[:500]}...")  # 截断避免过长

        # 4. 风险预警
        if "RISK_WARNINGS" in ai_texts:
            text = re.sub(r'<[^>]+>', ' ', ai_texts['RISK_WARNINGS'])
            text = re.sub(r'\s+', ' ', text).strip()
            parts.append(f"【风险预警】\n{text}")

        # 5. 操作策略
        if "OPERATION_STRATEGY" in ai_texts:
            parts.append(f"【操作策略】\n{ai_texts['OPERATION_STRATEGY']}")

        # 6. 市场数据特征
        if market_data:
            yesterday = market_data.get("yesterday", {})
            if yesterday:
                parts.append(f"【市场数据】\n{json.dumps(yesterday, ensure_ascii=False, indent=2)[:500]}")

        return "\n\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="早报编排工作流")
    parser.add_argument("--work-dir", default=DEFAULT_WORK_DIR, help="工作目录")
    parser.add_argument("--from-step", default=None, choices=STEPS, help="从指定步骤开始（断点续跑）")
    parser.add_argument("--skip-deploy", action="store_true", help="跳过 Cloudflare 部署")
    parser.add_argument("--skip-push", action="store_true", help="跳过飞书推送")
    args = parser.parse_args()

    workflow = MorningBriefWorkflow(work_dir=args.work_dir)
    result = workflow.run(
        from_step=args.from_step,
        skip_deploy=args.skip_deploy,
        skip_push=args.skip_push,
    )

    # 输出结果 JSON
    result_path = os.path.join(args.work_dir, "workflow_result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n[Workflow] 结果已保存: {result_path}")
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
