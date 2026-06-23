"""
shared/ai 包：LLM 相关能力。

模块：
- llm_client: LLM 客户端（DeepSeek 在线 + 离线回退）
- tools: Tool 封装（现有脚本 → 可调用工具）
"""

from .llm_client import LLMClient, LLMResponse
from .tools import FetchDataTool, PreparePromptTool, CompileTool, RenderReportTool, DeployCloudflareTool, PushFeishuTool

__all__ = [
    "LLMClient", "LLMResponse",
    "FetchDataTool", "PreparePromptTool", "CompileTool",
    "RenderReportTool", "DeployCloudflareTool", "PushFeishuTool",
]
