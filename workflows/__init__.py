"""
workflows 包：编排多个 Agent 完成完整任务。

架构原则：
- Agent 不互调，由 workflow 编排
- workflow 负责状态管理、断点续跑、并发调度
- 每个 workflow 对应一个完整业务场景
"""

from .morning_brief import MorningBriefWorkflow

__all__ = ["MorningBriefWorkflow"]
