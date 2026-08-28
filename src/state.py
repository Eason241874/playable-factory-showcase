# -*- coding: utf-8 -*-
"""全局状态定义：贯穿 LangGraph 各节点的共享状态。"""

import operator
from typing import Annotated, Any, Dict, List, TypedDict


class TraceEvent(TypedDict, total=False):
    """可序列化的节点级观测事件，便于面试演示和失败定位。"""

    node: str
    status: str
    duration_ms: float
    fix_round: int
    error: str


class AdState(TypedDict, total=False):
    # ---- 输入 ----
    brief: str                     # 策划文档原文

    # ---- 需求解析 Agent 输出 ----
    spec: Dict[str, Any]           # 结构化需求 spec

    # ---- 玩法规划 Agent 输出 ----
    plan: Dict[str, Any]           # 玩法路径规划（含组件选择）

    # ---- 组件匹配 Agent 输出 ----
    components: List[Dict[str, Any]]  # RAG 命中的组件条目
    rag_fallback: bool             # 是否发生检索降级

    # ---- 代码生成 Agent 输出 ----
    params: Dict[str, Any]         # 组件/玩法参数取值
    custom_logic: str              # LLM 生成的定制玩法逻辑（未注册玩法时）

    # ---- 自测 Agent 输出 ----
    qa_report: Dict[str, Any]      # 自测报告
    fix_rounds: int                # 已修复轮数

    # ---- 人工审核 ----
    human_review: Dict[str, Any]   # 审核记录

    # ---- 产出 ----
    html: str                      # 最终单文件 H5
    output_path: str

    # ---- 元信息 ----
    mock: bool
    errors: List[str]
    run_id: str
    trace: Annotated[List[TraceEvent], operator.add]
    # log 用 operator.add 做 reducer：每个节点返回的增量日志
    # 追加到历史日志后面，而不是互相覆盖。LangGraph 默认是整体覆盖，
    # 不写 reducer 的话最后只剩 human_review 一条，排查问题全靠猜。
    log: Annotated[List[str], operator.add]
