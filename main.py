# -*- coding: utf-8 -*-
"""Playable Factory CLI：需求 brief -> 多 Agent -> 单文件 H5 + QA 报告。"""

from __future__ import annotations

import argparse
import io
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

# Windows 控制台统一 UTF-8，保证中文日志在面试演示时可读。
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.graph import build_graph
from src.telemetry import trace_summary

ROOT = Path(__file__).resolve().parent


def _resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def run(brief: str, *, mock: bool, with_review: bool, out_path: str) -> Dict[str, Any]:
    """执行一次可复现流水线；mock 模式不访问网络。"""

    graph = build_graph()
    app = graph.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["human_review"] if with_review else [],
    )
    config = {"configurable": {"thread_id": f"run-{uuid.uuid4().hex[:10]}"}}
    state = app.invoke(
        {
            "brief": brief,
            "mock": mock,
            "fix_rounds": 0,
            "log": [],
            "trace": [],
            "errors": [],
            "run_id": config["configurable"]["thread_id"],
        },
        config,
    )

    if with_review:
        report = state.get("qa_report", {})
        print("\n" + "=" * 56)
        print("流水线已在【人工审核】节点暂停")
        print("=" * 56)
        print("  玩法模板 : %s" % state.get("plan", {}).get("mechanic"))
        print("  启用组件 : %s" % ", ".join(c["name"] for c in state.get("components", [])))
        print("  自测得分 : %s / 100" % report.get("score", "-"))
        if report.get("fails"):
            print("  阻断问题 : %s" % ", ".join(report["fails"]))
        try:
            answer = input("\n  审核是否通过？(y=通过 / n=打回) [y]: ").strip().lower()
        except EOFError:
            answer = ""
        if answer in ("n", "no"):
            app.update_state(config, {"human_review": {"status": "rejected"}, "log": ["[review] 人工打回"]})
            print("已打回，本次不落盘产出。")
            return app.get_state(config).values
        state = app.invoke(Command(resume="approved"), config)

    output = _resolve(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(state.get("html", ""), encoding="utf-8")
    report_path = output.with_name(output.stem + "_qa_report.json")
    report_path.write_text(
        json.dumps(state.get("qa_report", {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n产出完成")
    print("  H5      : %s (%.1f KB)" % (output, len(state.get("html", "").encode("utf-8")) / 1024))
    print("  自测报告: %s" % report_path)
    print("  Trace   : %s" % json.dumps(trace_summary(state), ensure_ascii=False))
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Playable Factory 多 Agent 试玩广告生产系统")
    parser.add_argument("--brief", default="examples/brief_merge.txt", help="策划 brief 路径")
    parser.add_argument("--out", default="outputs/playable.html", help="H5 输出路径")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true", help="离线可复现模式（默认）")
    mode.add_argument("--live", action="store_true", help="调用 OpenAI 兼容接口")
    parser.add_argument("--no-review", action="store_true", help="跳过人工审核，适合 CI/演示")
    args = parser.parse_args()

    brief_path = _resolve(args.brief)
    if not brief_path.exists():
        parser.error(f"brief 不存在: {brief_path}")
    brief = brief_path.read_text(encoding="utf-8")
    state = run(
        brief,
        mock=not args.live,
        with_review=not args.no_review,
        out_path=args.out,
    )

    print("\n--- 流水线日志 ---")
    for line in state.get("log", []):
        print(" ", line)


if __name__ == "__main__":
    main()
