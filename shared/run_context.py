#!/usr/bin/env python3
"""运行时上下文：用 contextvar 传递 run_id 贯穿全链路"""
import uuid
from contextvars import ContextVar
from typing import Optional

# 全局上下文变量
_run_id: ContextVar[Optional[str]] = ContextVar('run_id', default=None)

def get_run_id() -> str:
    """获取当前 run_id，若无则自动生成"""
    rid = _run_id.get()
    if rid is None:
        rid = str(uuid.uuid4())[:8]
        _run_id.set(rid)
    return rid

def set_run_id(rid: str):
    """显式设置 run_id"""
    _run_id.set(rid)

def new_run_id() -> str:
    """生成新 run_id 并设置到上下文"""
    rid = str(uuid.uuid4())[:8]
    _run_id.set(rid)
    return rid
