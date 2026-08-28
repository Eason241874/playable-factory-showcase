# -*- coding: utf-8 -*-
"""五个专业 Agent 节点：需求解析 / 玩法规划 / 组件匹配 / 代码生成 / 自测闭环。
每个节点都是一个纯函数：读 state，返回增量更新。"""

import json
import re
from typing import Any, Dict

from src.llm import LLMClient
from src.rag import ComponentRetriever, load_library

# =================================================================
# Agent 1：需求语义解析 —— 策划文档 → 结构化 spec
# =================================================================

PARSE_SYSTEM = """你是试玩广告(playable ad)需求分析专家。把创意策划文档解析为结构化 JSON：
{
 "title": "广告标题(<=12字)", "desc": "开始页一句话描述(<=30字)",
 "mechanic_hint": "核心玩法归类，优先从 drag_merge/stack_build/sort_puzzle/tomb_explore 中选，都不符合则填 custom",
 "core_loop": "一句话核心循环", "target": "胜利条件", "fail": "失败条件(可空)",
 "tone": "美术调性关键词", "item_name": "道具名", "cta_text": "CTA按钮文案",
 "countdown_seconds": 数字或null, "theme_bg": "CSS背景(可空)", "cta_url": "跳转链接(可空)"
}
只输出 JSON。"""

# mock 模式：关键词规则解析（离线可复现），顺序即优先级
_MOCK_RULES = [
    (("古墓", "探测", "寻宝", "宝藏", "tomb", "treasure", "挖掘", "探险"), "tomb_explore"),
    (("热气球", "气球", "救援", "下落", "高空", "balloon", "rescue", "拆螺丝", "修复"), "balloon_rescue"),
    (("合成", "merge", "二合", "装修"), "drag_merge"),
    (("叠塔", "stack", "叠上", "叠满", "层"), "stack_build"),
    (("分拣", "分类", "sort"), "sort_puzzle"),
]


def parse_agent(state) -> Dict[str, Any]:
    brief = state["brief"]
    if state.get("mock"):
        mechanic = "custom"
        for kws, m in _MOCK_RULES:
            if any(k in brief for k in kws):
                mechanic = m
                break
        spec = _mock_spec(brief, mechanic)
        return {"spec": spec, "log": ["[parse] mock 规则解析完成 -> mechanic_hint=%s" % mechanic]}

    llm = LLMClient()
    spec = llm.chat_json(PARSE_SYSTEM, "策划文档：\n" + brief)
    return {"spec": spec, "log": ["[parse] LLM 语义解析完成"]}


# 各玩法的 mock 解析结果：brief 里抽不出来的字段给一套
# 经过投放验证的默认值，保证离线演示产物的完成度
_MOCK_SPEC_DEFAULTS = {
    "tomb_explore": {
        "desc": "拖动探测仪，挖出古墓里的全部宝藏！",
        "core_loop": "拖动探测仪扫描墓墙，点击挖掘宝藏",
        "target": "集齐 3 只宝箱",
        "fail": "挖到僵尸或倒计时结束",
        "tone": "暗黑墓室、烛光、探险",
        "item_name": "宝箱",
        "theme_bg": "",
        "coin_target": 99999,
        "end_success": "恭喜通关！古墓宝藏尽收囊中",
        "end_success_sub": "完整版还有更多古墓等着你",
        "end_fail": "就差一点！",
        "end_fail_sub": "再扫描时离僵尸远一点",
    },
    "drag_merge": {
        "desc": "拖动相同道具进行合成，打造你的梦幻豪宅！",
        "core_loop": "拖拽同级道具合成更高级道具",
        "target": "合成到目标等级或完成指定合成次数",
        "fail": "倒计时结束未完成",
        "tone": "明亮、卡通、治愈",
        "item_name": "家具",
        "theme_bg": "linear-gradient(160deg,#11998e,#38ef7d)",
    },
    "balloon_rescue": {
        "desc": "气球正在坠落！选对道具，拆螺丝修好它！",
        "core_loop": "选择修复道具，拆螺丝解开破损部位",
        "target": "倒计时内修完三处破损",
        "fail": "倒计时归零气球坠落",
        "tone": "高空、蓝天、轻悬疑",
        "item_name": "修复道具",
        "theme_bg": "",
        "end_success": "救援成功！气球安全落地",
        "end_success_sub": "完整版还有更惊险的高空救援",
        "end_fail": "气球坠落了……",
        "end_fail_sub": "再试一次，动作快一点！",
    },
}


def _mock_spec(brief: str, mechanic: str) -> Dict[str, Any]:
    """mock 规则解析：从 brief 抽标题/倒计时，其余按玩法默认表补齐。

    倒计时抽取有个坑：brief 里常出现"3 秒上手""25~40 秒一局"这类
    干扰数字，所以先抓"N秒倒计时/倒计时N秒"的强模式，抓不到再退到
    "大于 5 秒的第一个数字"——小于等于 5 的默认是教学话术，不是时长。
    """
    title = re.search(r"《(.+?)》", brief)
    cd = re.search(r"(\d+)\s*秒\s*倒计时", brief) or re.search(r"倒计时\s*(\d+)\s*秒", brief)
    if not cd:
        for m in re.finditer(r"(\d+)\s*秒", brief):
            if int(m.group(1)) > 5:
                cd = m
                break
    spec = {
        "title": title.group(1) if title else "古墓寻宝记",
        "mechanic_hint": mechanic,
        "cta_text": "立即下载",
        "countdown_seconds": int(cd.group(1)) if cd else 30,
        "cta_url": "",
    }
    spec.update(_MOCK_SPEC_DEFAULTS.get(mechanic, _MOCK_SPEC_DEFAULTS["drag_merge"]))
    return spec


# =================================================================
# Agent 2：核心玩法路径规划 —— spec → 分阶段玩法 plan + 组件选择
# =================================================================

PLAN_SYSTEM_TMPL = """你是试玩广告玩法策划。基于结构化需求，规划 15-30 秒可跑通的最小玩法路径。
可用玩法模板：{mechanics}
可用增强组件：{components}
输出 JSON：
{{
 "mechanic": "玩法模板名(优先复用已有模板；都不合适填 custom)",
 "custom_reason": "选 custom 时说明原因，否则为空",
 "stages": [{{"stage": "阶段名", "goal": "目标", "interactions": ["交互1"]}}],
 "components": ["要启用的组件名，从可用组件中选，宁缺毋滥"],
 "success_rule": "胜利判定", "fail_rule": "失败判定",
 "difficulty": "给代码生成 Agent 的难度建议(数值层面)"
}}
只输出 JSON。"""


def plan_agent(state) -> Dict[str, Any]:
    spec = state["spec"]
    lib = load_library()
    if state.get("mock"):
        mechanic = spec.get("mechanic_hint", "custom")
        known = {m["name"] for m in lib.get("mechanics", [])}
        if mechanic not in known and mechanic != "custom":
            mechanic = "custom"
        comps = ["hint_hand"]
        if spec.get("countdown_seconds"):
            comps.append("countdown")
        if mechanic in ("drag_merge", "sort_puzzle"):
            comps.append("progress_bar")
        if mechanic == "tomb_explore":
            # 探测寻宝的黄金组合：金币计数器（奖励反馈）+ 任务横幅（3 箱目标感）
            comps += ["coin_counter", "task_goal"]
        if mechanic == "balloon_rescue":
            # 救援玩法的压力结构：倒计时（全局坠落线）+ 引导手（点气球开场）
            comps += ["hint_hand", "screen_shake"]
        if mechanic == "stack_build":
            comps.append("combo_text")
        # 冲突组件去重：task_goal 与 progress_bar 只留先声明的那个
        seen = []
        for c in comps:
            entry = next((x for x in lib.get("components", []) if x["name"] == c), None)
            if entry and set(entry.get("conflicts", []) or []) & set(seen):
                continue
            if c not in seen:
                seen.append(c)
        plan = {
            "mechanic": mechanic,
            "custom_reason": "",
            "stages": [
                {"stage": "吸引", "goal": "3秒内明白玩法", "interactions": ["看引导手"]},
                {"stage": "上手", "goal": "完成首次核心操作", "interactions": ["首次操作"]},
                {"stage": "冲刺", "goal": "在倒计时内达成目标", "interactions": ["连续操作"]},
            ],
            "components": seen,
            "success_rule": spec.get("target", "达成关卡目标"),
            "fail_rule": spec.get("fail", "倒计时归零"),
            "difficulty": "target_level=4, total=5, 倒计时 30s，新手 20s 内可完成",
        }
        return {"plan": plan, "log": ["[plan] mock 规划完成 -> %s, 组件 %s" % (mechanic, seen)]}

    llm = LLMClient()
    system = PLAN_SYSTEM_TMPL.format(
        mechanics=json.dumps(
            ["%s:%s（适合:%s）" % (m["name"], m["description"], m.get("best_for", ""))
             for m in lib["mechanics"]], ensure_ascii=False),
        components=json.dumps(
            ["%s:%s（冲突:%s）" % (c["name"], c["when"], ",".join(c.get("conflicts", []) or []) or "无")
             for c in lib["components"]], ensure_ascii=False),
    )
    plan = llm.chat_json(system, "结构化需求：\n" + json.dumps(spec, ensure_ascii=False, indent=2))
    if not plan.get("mechanic"):
        plan["mechanic"] = spec.get("mechanic_hint", "custom")
    # LLM 偶尔也会把冤家组件一起选上，这里统一拦一道
    chosen, dropped = [], []
    lib_by_name = {c["name"]: c for c in lib.get("components", [])}
    for name in plan.get("components", []) or []:
        entry = lib_by_name.get(name)
        if entry and set(entry.get("conflicts", []) or []) & set(chosen):
            dropped.append(name)
            continue
        chosen.append(name)
    plan["components"] = chosen
    log = ["[plan] LLM 玩法规划完成 -> %s" % plan.get("mechanic")]
    if dropped:
        log.append("[plan] 冲突组件已剔除: %s" % ", ".join(dropped))
    return {"plan": plan, "log": log}


# =================================================================
# Agent 3：组件素材匹配 —— RAG 检索历史高点击组件（含降级）
# =================================================================

def component_agent(state) -> Dict[str, Any]:
    spec, plan = state["spec"], state["plan"]
    query = " ".join([
        spec.get("title", ""), spec.get("tone", ""), spec.get("core_loop", ""),
        plan.get("success_rule", ""), " ".join(spec.get("desc", "").split()),
    ])
    retriever = ComponentRetriever(mock=state.get("mock", False))
    wanted = plan.get("components", []) or []
    hits = retriever.retrieve(query, top_k=max(3, len(wanted)),
                              mechanic=plan.get("mechanic"), boost=wanted)
    # 以规划阶段点名 + 检索命中的交集为准；点名的必须带上
    by_name = {c["name"]: c for c in hits}
    chosen = []
    for name in wanted:
        if name in by_name:
            chosen.append(by_name[name])
        else:
            lib_c = next((c for c in retriever.components if c["name"] == name), None)
            if lib_c:
                chosen.append(dict(lib_c, score=None))
    if not chosen:
        chosen = hits[:2]  # 规划没点名时，用检索 top2 兜底
    # 保留“规划点名优先”的召回边界，但最终按可解释 score 输出，
    # 让日志、QA 和面试演示都能直接看到排序结果。
    chosen.sort(key=lambda item: item.get("score") if item.get("score") is not None else -1, reverse=True)
    log = ["[component] RAG(%s) 命中: %s" % (
        retriever.embedder.provider,
        ", ".join("%s(%s)" % (c["name"], c.get("score")) for c in chosen))]
    return {"components": chosen, "rag_fallback": retriever.embedder.provider == "local-hash",
            "log": log}


# =================================================================
# Agent 4：代码逻辑生成 —— 组装模板/组件/参数，产出单文件 H5
# =================================================================

CODEGEN_SYSTEM = """你是 H5 试玩广告前端专家。基于玩法规划与骨架接口，为"custom"玩法编写核心玩法 JS。
骨架提供：App.cfg(参数对象)、App.state、App.act()(每次有效操作调用)、App.emit('cleared')(每次进度+1调用)、
App.end('success'|'fail')、on('start'|'end',fn)、el(id)。骨架已含开始页/结算页/CTA，你只写 #game-layer 内的玩法。
另输出该玩法需要的 HTML(放入 #game-layer)与 CSS。
输出 JSON：{"html":"...","css":"...","js":"...","params":{"total":数字,...}}，js 中不要包含 <script> 标签。"""


def codegen_agent(state) -> Dict[str, Any]:
    spec, plan = state["spec"], state["plan"]
    mechanic = plan["mechanic"]
    update: Dict[str, Any] = {}

    # 参数推导：玩法核心参数 + 组件参数默认值 + spec 覆盖
    lib = load_library()
    mech_def = next((m for m in lib.get("mechanics", []) if m["name"] == mechanic), None)
    params: Dict[str, Any] = {}
    if mech_def:
        for k, p in mech_def.get("core_params", {}).items():
            params[k] = p.get("default")
    for c in state.get("components", []):
        for k, p in c.get("params", {}).items():
            params[k] = p.get("default")
    if spec.get("countdown_seconds") and "countdown_seconds" in params:
        params["countdown_seconds"] = spec["countdown_seconds"]
    if mechanic == "drag_merge":
        params.setdefault("item_emojis", ["📦", "🪑", "🛋️", "🛏️", "🏠", "🏰"])
        params.setdefault("item_name", spec.get("item_name", "家具"))
    if mechanic == "tomb_explore":
        # 素材 data URI 走 params 灌给组件（金币计数器要吃 img_coin），
        # 玩法模板自身的 img_xxx 占位符由 renderer 统一注入
        try:
            from components.tomb_assets import ASSETS
            params.setdefault("img_coin", ASSETS.get("coin", ""))
        except Exception:
            pass
        # CTA 链接进 cfg，模板里的 __openStore 三级降级链要用
        params.setdefault("cta_url", spec.get("cta_url", ""))
        # 通关金币线灌给计数器组件显示（模板内部 GOAL 与之一致）
        params.setdefault("coin_target", spec.get("coin_target", 99999))
        # brief 里写明的雷数/箱数优先（mock 模式抽不到就吃库里的默认值）
        zm = re.search(r"(\d+)\s*(?:只|个)?僵尸", state.get("brief", ""))
        if zm:
            params["zombie_count"] = int(zm.group(1))
        ch = re.search(r"(\d+)\s*(?:只|个)宝箱", state.get("brief", ""))
        if ch:
            params["chest_target"] = int(ch.group(1))

    if mechanic == "balloon_rescue":
        params.setdefault("cta_url", spec.get("cta_url", ""))

    if mechanic == "custom":
        if state.get("mock"):
            # mock：复用叠塔模板兜底，保证离线也能产出可玩 H5
            update["log"] = ["[codegen] mock: custom 玩法降级复用 stack_build 模板"]
            state_patch = {"plan": {**plan, "mechanic": "stack_build"}}
            update.update(state_patch)
        else:
            llm = LLMClient()
            out = llm.chat_json(CODEGEN_SYSTEM, "玩法规划：\n" + json.dumps(plan, ensure_ascii=False, indent=2),
                                temperature=0.5)
            update.update({
                "custom_html": out.get("html", ""), "custom_css": out.get("css", ""),
                "custom_logic": out.get("js", ""),
                "log": ["[codegen] LLM 生成 custom 玩法逻辑，%d 字符" % len(out.get("js", ""))],
            })
            params.update(out.get("params") or {})

    update["params"] = params
    # 渲染装配（模板 + 组件片段 + 骨架）
    tmp_state = {**state, **update}
    from src.renderer import render
    update["html"] = render(tmp_state)
    update.setdefault("log", [])
    update["log"] = update["log"] + ["[codegen] 渲染完成，H5 大小 %d 字符" % len(update["html"])]
    return update


# =================================================================
# Agent 5：自测闭环 —— 静态校验 + 自动修复循环
# =================================================================

MAX_FIX_ROUNDS = 3

REQUIRED_SNIPPETS = ["App.emit('start')", "App.end(", "track('click_cta')", "id=\"btn-start\""]

# 量产级 QA 规则：每项检查有严重级别 BLOCKER / WARNING / INFO。
# 使用可读的 predicate，避免把规则拼成 eval 字符串。
_PROD_CHECKS = [
    ("非空", lambda h, s: len(h) > 500, "BLOCKER"),
    ("单文件结构", lambda h, s: all(t in h for t in ("<!DOCTYPE html", "</html>", "<style>", "<script>")), "BLOCKER"),
    ("开始页", lambda h, s: 'id="start-layer"' in h and 'id="btn-start"' in h, "BLOCKER"),
    ("结算页", lambda h, s: 'id="end-layer"' in h, "BLOCKER"),
    ("CTA 按钮与埋点", lambda h, s: 'id="btn-cta"' in h and "track('click_cta')" in h, "BLOCKER"),
    ("胜利路径可达", lambda h, s: "App.end('success')" in h or 'App.end("success")' in h, "BLOCKER"),
    ("渠道三轨跳转", lambda h, s: "window.__openStore" in h and "ExitApi" in h and "mraid" in h, "BLOCKER"),
    ("CTA 隐形热区", lambda h, s: 'id="cta-hotzone"' in h, "BLOCKER"),
    ("无占位符残留", lambda h, s: "{{" not in h, "BLOCKER"),
    ("安全区 CSS", lambda h, s: "safe-area-inset" in h, "WARNING"),
    ("横竖屏适配", lambda h, s: "@media (orientation: landscape)" in h, "WARNING"),
    ("音效引擎", lambda h, s: "AudioContext" in h, "WARNING"),
    ("MRAID modal 守护", lambda h, s: "MutationObserver" in h, "WARNING"),
    ("DPR 感知渲染", lambda h, s: "devicePixelRatio" in h, "WARNING"),
    ("Canvas 渲染", lambda h, s: "<canvas" in h, "WARNING"),
    ("包体 <= 5MB", lambda h, s: s <= 5000, "INFO"),
]


def _qa_check(html: str, state) -> Dict[str, Any]:
    """静态质检规则 v2：量产级 —— BLOCKER/WARNING/INFO 三级严重度。"""
    checks, fails = [], []

    def chk(name, ok, detail="", severity="BLOCKER"):
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "severity": severity})
        if not ok and severity == "BLOCKER":
            fails.append(name)

    size_kb = len(html.encode("utf-8")) / 1024
    js_all = "".join(re.findall(r"<script[^>]*>(.*?)</script>", html, re.S))

    for name, predicate, severity in _PROD_CHECKS:
        ok = predicate(html, size_kb)
        detail = "%.1f KB" % size_kb if name == "包体 <= 5MB" else ""
        chk(name, ok, detail, severity)

    # JS 大括号配平
    chk("JS 大括号配平", js_all.count("{") == js_all.count("}"),
        "%d open / %d close" % (js_all.count("{"), js_all.count("}")), "BLOCKER")

    # 组件闭环
    for c in state.get("components", []):
        chk("组件已注入: %s" % c["name"],
            "[component: %s]" % c["name"] in html)

    for s in REQUIRED_SNIPPETS:
        chk("必需片段: %s" % s, s in html)

    score = round(100 * (len(checks) - len(fails)) / max(1, len(checks)))
    return {"passed": not fails, "score": score, "checks": checks, "fails": fails}


def qa_agent(state) -> Dict[str, Any]:
    report = _qa_check(state.get("html", ""), state)
    status = "PASS" if report["passed"] else "FAIL"
    log = ["[qa] %s score=%s fails=%s" % (status, report["score"], report["fails"])]
    # 自动修复：模拟一次修复循环（真实场景下将 fails 反馈给 codegen 重新生成）
    rounds = state.get("fix_rounds", 0)
    if not report["passed"] and rounds < MAX_FIX_ROUNDS:
        html = _auto_fix(state.get("html", ""), report["fails"], state)
        report2 = _qa_check(html, state)
        log.append("[qa] 自动修复第 %d 轮 -> %s" % (rounds + 1, "PASS" if report2["passed"] else "FAIL"))
        return {"html": html, "qa_report": report2, "fix_rounds": rounds + 1, "log": log}
    return {"qa_report": report, "log": log}


def _auto_fix(html: str, fails, state) -> str:
    """规则级自动修复兜底：补注入缺失组件、补埋点。"""
    for c in state.get("components", []):
        key = "组件已注入: %s" % c["name"]
        if key in fails:
            from components import snippets
            snippet = snippets.JS.get(c["name"], "")
            if snippet:
                html = html.replace("</body>", "<script>%s</script></body>" % snippet)
    if "必需片段: track('click_cta')" in fails:
        html = html.replace("</body>", "<script>el('btn-cta')&&el('btn-cta').addEventListener('click',function(){track('click_cta')})</script></body>")
    return html
