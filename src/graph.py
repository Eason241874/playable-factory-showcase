# -*- coding: utf-8 -*-
"""LangGraph 状态机编排：五个 Agent + 人工审核节点 + 条件路由。

流程：
  parse → plan → component → codegen → qa ──pass──> human_review → END
                                        ↑──fail(轮数内)──┘
                                        └──fail(超轮数)──> human_review(带降级标记)
"""

from langgraph.graph import END, StateGraph

from src.agents import codegen_agent, component_agent, parse_agent, plan_agent, qa_agent
from src.state import AdState
from src.telemetry import traced


def human_review_node(state: AdState):
    """人工审核占位节点。

    主入口在编译图时注入 interrupt_before=["human_review"]，
    图执行到这里会暂停，等待人工确认后以 Command 恢复。
    该函数本身只在审核通过后把审核记录写回状态。
    """
    return {
        "human_review": {
            "status": "approved",
            "qa_score": state.get("qa_report", {}).get("score"),
        },
        "log": ["[review] 人工审核通过，进入产出环节"],
    }


def qa_route(state: AdState) -> str:
    """自测结果路由：通过→人工审核；未通过且未超轮数→回炉 codegen。"""
    report = state.get("qa_report", {})
    if report.get("passed"):
        return "human_review"
    if state.get("fix_rounds", 0) >= 3:
        return "human_review"  # 超轮数降级交人工处置
    return "codegen"


def build_graph():
    g = StateGraph(AdState)
    # 每个节点都记录耗时，生成的 trace 会随着状态一起流转。
    g.add_node("parse", traced("parse", parse_agent))
    g.add_node("plan", traced("plan", plan_agent))
    g.add_node("component", traced("component", component_agent))
    g.add_node("codegen", traced("codegen", codegen_agent))
    g.add_node("qa", traced("qa", qa_agent))
    g.add_node("human_review", traced("human_review", human_review_node))

    g.set_entry_point("parse")
    g.add_edge("parse", "plan")
    g.add_edge("plan", "component")
    g.add_edge("component", "codegen")
    g.add_edge("codegen", "qa")
    g.add_conditional_edges("qa", qa_route, {"human_review": "human_review", "codegen": "codegen"})
    g.add_edge("human_review", END)
    return g
