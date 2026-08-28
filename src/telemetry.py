# -*- coding: utf-8 -*-
"""轻量节点观测：不依赖外部 tracing 服务，适合离线演示和 CI。"""

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable, Dict


def traced(node_name: str, node: Callable[[Dict[str, Any]], Dict[str, Any]]):
    """给 LangGraph node 加上耗时/异常记录，同时保留原 node 的纯函数形态。"""

    def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
        started = perf_counter()
        try:
            update = node(state) or {}
        except Exception as exc:
            event = {
                "node": node_name,
                "status": "error",
                "duration_ms": round((perf_counter() - started) * 1000, 2),
                "fix_round": int(state.get("fix_rounds", 0) or 0),
                "error": f"{type(exc).__name__}: {exc}",
            }
            # trace 使用 reducer 追加，既保留上下文又不吞掉原始异常。
            raise RuntimeError(f"node={node_name} failed: {exc}") from exc

        event = {
            "node": node_name,
            "status": "ok",
            "duration_ms": round((perf_counter() - started) * 1000, 2),
            "fix_round": int(update.get("fix_rounds", state.get("fix_rounds", 0)) or 0),
        }
        return {**update, "trace": [event]}

    wrapper.__name__ = getattr(node, "__name__", node_name)
    return wrapper


def trace_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    """把 trace 压缩成适合 CLI/README 展示的一行摘要。"""

    events = state.get("trace", []) or []
    total = round(sum(float(e.get("duration_ms", 0)) for e in events), 2)
    return {
        "nodes": len(events),
        "total_duration_ms": total,
        "failed_nodes": [e.get("node") for e in events if e.get("status") != "ok"],
    }
