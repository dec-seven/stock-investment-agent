"""
Agent 基类与核心抽象。

设计要点：
- BaseAgent：统一 Agent 接口（name/tools/llm_client/run）
- AgentResult：标准化输出（success/data/errors/trace）
- Tool：工具基类，封装现有脚本为可调用单元
- ToolResult：工具执行结果

双模式 LLM：
- 在线模式（DEEPSEEK_API_KEY 存在）：调 DeepSeek API，自动重试
- 离线模式（无 API Key）：生成 prompt 文件，等待外部执行，读取结果 JSON
  —— 兼容现有"人肉协议"，Agent 架构落地不阻塞
"""

import os
import json
import time
import uuid
import subprocess
from dataclasses import dataclass, field
from typing import Any, Optional

# 项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Any = None
    error: str = ""
    duration_ms: int = 0

    def __bool__(self):
        return self.success


@dataclass
class AgentResult:
    """Agent 标准化输出"""
    success: bool
    agent_name: str
    data: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    trace: list = field(default_factory=list)  # [{step, tool, duration_ms, ok}]
    run_id: str = ""

    def add_trace(self, step: str, tool: str, duration_ms: int, ok: bool):
        self.trace.append({"step": step, "tool": tool, "duration_ms": duration_ms, "ok": ok})

    def add_error(self, err: str):
        self.errors.append(err)


class Tool:
    """工具基类：封装现有脚本为可调用单元。

    子类需实现 execute()，返回 ToolResult。
    """

    name: str = "base_tool"

    def __init__(self, run_id: str = ""):
        self.run_id = run_id

    def execute(self, **kwargs) -> ToolResult:
        raise NotImplementedError

    def _run_script(self, cmd: list, timeout: int = 180) -> ToolResult:
        """运行外部脚本，返回 ToolResult。

        Args:
            cmd: 命令列表，如 ["python3", "fetch_data.py", "--output", "/tmp/x.json"]
            timeout: 超时秒数
        """
        start = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=PROJECT_ROOT,
            )
            duration_ms = int((time.time() - start) * 1000)
            if proc.returncode != 0:
                return ToolResult(
                    success=False,
                    error=f"脚本退出码 {proc.returncode}: {proc.stderr[:500]}",
                    duration_ms=duration_ms,
                )
            return ToolResult(success=True, data=proc.stdout, duration_ms=duration_ms)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error=f"超时 {timeout}s", duration_ms=int((time.time() - start) * 1000))
        except Exception as e:
            return ToolResult(success=False, error=str(e), duration_ms=int((time.time() - start) * 1000))


class BaseAgent:
    """Agent 基类。

    子类需实现 run()，返回 AgentResult。
    通过 self.tools 字典访问工具，self.llm 调用 LLM。
    """

    name: str = "base_agent"
    description: str = ""

    def __init__(self, llm_client=None, tools: dict = None, run_id: str = ""):
        self.llm = llm_client
        self.tools = tools or {}
        self.run_id = run_id or str(uuid.uuid4())[:8]

    def run(self, input_data: dict) -> AgentResult:
        raise NotImplementedError

    def call_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """调用工具并记录"""
        tool = self.tools.get(tool_name)
        if not tool:
            return ToolResult(success=False, error=f"工具不存在: {tool_name}")
        tool.run_id = self.run_id
        return tool.execute(**kwargs)
