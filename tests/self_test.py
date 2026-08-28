# -*- coding: utf-8 -*-
"""离线自测：节点行为、RAG、渲染、QA 与端到端 LangGraph。"""

from __future__ import annotations

import json
import io
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from langgraph.checkpoint.memory import MemorySaver

from src.agents import codegen_agent, component_agent, parse_agent, plan_agent, qa_agent
from src.graph import build_graph
from src.llm import parse_json
from src.rag import ComponentRetriever
from src.telemetry import trace_summary
from tools.audit_html import audit


results = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition)))
    mark = "✅" if condition else "❌"
    print(f"{mark} {name}{(': ' + detail) if detail else ''}")


def make_state(brief: str) -> dict:
    return {"brief": brief, "mock": True, "fix_rounds": 0, "log": [], "errors": [], "trace": []}


def run_linear(brief: str) -> dict:
    state = make_state(brief)
    state.update(parse_agent(state))
    state.update(plan_agent(state))
    state.update(component_agent(state))
    state.update(codegen_agent(state))
    state.update(qa_agent(state))
    return state


merge_brief = (ROOT / "examples" / "brief_merge.txt").read_text(encoding="utf-8")
merge_state = run_linear(merge_brief)

check("mock parse 识别合成玩法", merge_state["spec"]["mechanic_hint"] == "drag_merge")
check("mock parse 抽取倒计时", merge_state["spec"]["countdown_seconds"] == 30)
check("plan 启用倒计时", "countdown" in merge_state["plan"]["components"])
check("plan 启用进度条", "progress_bar" in merge_state["plan"]["components"])
check("RAG 命中规划组件", len(merge_state["components"]) >= 3)
check("RAG score 有序", all(
    a["score"] >= b["score"] for a, b in zip(merge_state["components"], merge_state["components"][1:])
))
check("codegen 产出单文件 HTML", len(merge_state["html"]) > 3000)
check("无模板占位符残留", not re.search(r"\{\{[^}]+\}\}", merge_state["html"]))
check("包含 CTA 埋点", "track('click_cta')" in merge_state["html"])
check("QA 阻断项通过", merge_state["qa_report"]["passed"], str(merge_state["qa_report"]["fails"]))

with tempfile.TemporaryDirectory() as temp_dir:
    html_path = Path(temp_dir) / "merge.html"
    html_path.write_text(merge_state["html"], encoding="utf-8")
    report = audit(str(html_path))
    check("独立交付审计通过", report["passed"], str(report["blockers"]))

graph = build_graph().compile(checkpointer=MemorySaver(), interrupt_before=[])
final = graph.invoke(make_state(merge_brief), {"configurable": {"thread_id": "self-test-merge"}})
summary = trace_summary(final)
check("LangGraph 端到端产出", bool(final.get("html")))
check("LangGraph QA 通过", final.get("qa_report", {}).get("passed") is True)
check("Trace 覆盖至少 6 个节点", summary["nodes"] >= 6, json.dumps(summary, ensure_ascii=False))
check("Trace 有总耗时", summary["total_duration_ms"] >= 0)

stack_brief = (ROOT / "examples" / "brief_stack.txt").read_text(encoding="utf-8")
stack = run_linear(stack_brief)
check("第二个玩法模板可插拔", stack["plan"]["mechanic"] == "stack_build")
check("第二个玩法也能通过 QA", stack["qa_report"]["passed"] is True)

nested = parse_json('{"outer": {"items": [1, 2]}, "ok": true}')
check("JSON 解析支持嵌套对象", nested["outer"]["items"] == [1, 2])
try:
    parse_json("not json")
except ValueError:
    check("坏 JSON 明确失败", True)
else:
    check("坏 JSON 明确失败", False)

agents_source = (ROOT / "src" / "agents.py").read_text(encoding="utf-8")
check("QA 规则不使用动态 eval", "eval(" not in agents_source)

passed = sum(ok for _, ok in results)
print("\n" + "=" * 44)
print(f"自测完成: {passed}/{len(results)} 通过")
raise SystemExit(0 if passed == len(results) else 1)
