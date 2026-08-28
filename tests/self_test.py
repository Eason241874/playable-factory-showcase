# -*- coding: utf-8 -*-
"""离线自测：节点行为、RAG、渲染、QA 与端到端 LangGraph。"""

from __future__ import annotations

import json
import io
import re
import sys
import tempfile
import base64
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
from tools.skin_swap import EmbeddingAgent, ExtractAgent, ReplacementPlannerAgent


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
check("默认 demo 内嵌真实素材包", "merge_item_lv0" in merge_state["html"] and "data:image/png;base64" in merge_state["html"])
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

tiny_png = base64_1 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
blue_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAAC0lEQVR42mP8z8AARQAFAAH/e+m+AAAAAElFTkSuQmCC"
tiny_mp3 = "SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4LjQ1LjEwMAAAAAAAAAAAAAAA"
sample_html = f"""<!DOCTYPE html>
<html><head><style>.scene{{background-image:url(data:image/png;base64,{tiny_png});}}</style></head>
<body>
<button id="btn-start">start</button>
<div id="end-layer"></div>
<script>
var ExitApi = {{ exit: function(){{}} }};
var mraid = {{ open: function(){{}} }};
window.__openStore = function(){{}};
function track(name){{ return name; }}
var heroPlayer = 'data:image/png;base64,{tiny_png}';
var btn_play = 'data:image/png;base64,{blue_png}';
var bgm = 'data:audio/mpeg;base64,{tiny_mp3}';
var App = {{ emit: function(name){{ App.last = name; }}, end: function(result){{ App.result = result; }} }};
App.emit('start'); track('click_cta'); App.end('success');
</script>
</body></html>"""

with tempfile.TemporaryDirectory() as temp_dir:
    temp = Path(temp_dir)
    source = temp / "sample.html"
    bundle = temp / "skin_bundle"
    repl = temp / "new_hero.png"
    output = temp / "sample_skinned.html"
    source.write_text(sample_html, encoding="utf-8")
    repl.write_bytes(base64.b64decode(blue_png))

    manifest = ExtractAgent().run(source, bundle)
    check("换皮 Agent 提取并去重素材", manifest["total_assets"] == 3)
    check("换皮 Agent 自动分类图片/音频", {"scene", "ui", "audio"}.issubset(set(manifest["categories"])))

    request = {
        "replace": [
            {"match": {"role": "background"}, "with": str(repl), "limit": 1, "reason": "demo background swap"}
        ],
        "replace_edited_files": False,
    }
    plan = ReplacementPlannerAgent().run(manifest, request, bundle)
    check("换皮 Agent 生成替换计划", plan["replace_count"] == 1)

    report = EmbeddingAgent().run(manifest, plan, source, output)
    out_text = output.read_text(encoding="utf-8")
    check("换皮 Agent 回嵌新素材", report["embedded"][0]["occurrences"] == 2)
    check("换皮后仍为单文件 data URI", "data:image/png;base64," in out_text and "http://" not in out_text)
    check("换皮报告通过交付审计", report["audit"]["passed"], str(report["audit"].get("blockers")))

passed = sum(ok for _, ok in results)
print("\n" + "=" * 44)
print(f"自测完成: {passed}/{len(results)} 通过")
raise SystemExit(0 if passed == len(results) else 1)
