# Playable Factory

从玩法 brief 到单文件 H5 的试玩广告生产管线。它把玩法规划、组件复用、素材装配、QA 检查和换皮回嵌放进同一条可复现流程，适合用来展示 Playable Ads 的工程化制作能力。

> 公开仓库只保留可展示的 demo、流程代码和测试；实际渠道成品、音视频和投放素材包未放入仓库。Demo 美术使用 Kenney CC0 素材，来源见 [docs/asset_sources.md](docs/asset_sources.md)。

## Highlights

```text
brief.txt
   │
   ▼
Parse Agent ──► Plan Agent ──► Component Agent (RAG)
                                      │
                                      ▼
                              Codegen Agent
                                      │
                                      ▼
                  QA Agent ── pass ──► Human Review ──► H5
                      │
                      └── fail + remaining budget ──► Codegen
```

- 状态图编排：显式状态、条件路由和 QA 回炉环，能看清每一步为什么发生。
- 离线可复现：默认 `mock` 模式无需网络，适合面试展示、CI 和作品集演示。
- 组件召回：本地向量召回叠加玩法亲和度、冲突规则和历史先验，避免把整库硬塞进生成阶段。
- 单文件交付：玩法模板、公开素材包、组件片段和投放壳最终装配成一个 HTML。
- 质量门禁：检查结构、CTA、MRAID 降级链、模板残留、包体大小和动态执行风险。
- 人工验收：QA 通过后停在 `human_review` 节点，确认后再落盘。
- 换皮流水线：提取内嵌素材、自动分类、生成替换计划，再把新素材回嵌成单文件 H5。

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 完全离线，默认不访问网络；跳过人工审核用于演示/CI
python main.py --mock --no-review --brief examples/brief_merge.txt --out outputs/merge.html
```

用浏览器打开 `outputs/merge.html` 即可试玩；同目录会生成 `merge_qa_report.json`。`outputs/` 已被 `.gitignore` 忽略，避免把生成物误提交。

运行自测：

```powershell
python tests/self_test.py
```

换皮 Agent 示例：

```powershell
python tools/skin_swap.py extract path\to\playable.html --out-dir skin\demo
python tools/skin_swap.py plan skin\demo --request examples\skin_request.json
python tools/skin_swap.py embed skin\demo path\to\playable.html --out outputs\demo_skinned.html
```

它会生成 `manifest.json`、`asset_catalog.json`、`replacement_plan.json` 和
`.skin_report.json`，用于展示每个素材的分类、替换原因、引用次数和回嵌后的审计结果。

Live 模式只从环境变量读取凭据：

```powershell
$env:LLM_API_KEY = "在当前终端临时设置，不要写入文件"
$env:LLM_BASE_URL = "https://api.example.com/v1"
python main.py --live --no-review --brief examples/brief_merge.txt
```

仓库不会保存、读取或上传 `.env`；请勿把真实 key 粘贴进代码、README、Issue 或提交历史。

## Project map

```text
main.py                     # CLI、人工审核中断、产出 QA 报告
src/state.py                # LangGraph 共享状态与 reducer
src/graph.py                # Agent 节点、条件边、HITL 节点
src/telemetry.py            # 节点 trace 与运行摘要
src/agents.py               # parse / plan / component / codegen / QA
src/llm.py                  # mock/live 抽象与稳健 JSON 解析
src/rag.py                  # 哈希向量召回、规则重排、冲突处理
src/renderer.py             # H5 壳、模板与组件装配
src/demo_asset_pack.py      # 公开 demo 素材包加载器
src/templates/              # drag_merge / stack_build / balloon / tomb
components/library.yaml     # 玩法与增强组件知识库
components/snippets.py      # 可复用的前端组件片段
public_assets/kenney/       # Kenney CC0 demo assets and license files
tools/skin_swap.py          # 内嵌 data URI 素材提取/灌回工具
tools/audit_html.py         # 独立静态交付审计器
tests/self_test.py          # 离线节点测试 + 端到端 smoke test
```

换皮流水线的详细设计见 [docs/skin_swap_agent.md](docs/skin_swap_agent.md)。

## Design decisions

### 为什么不是一个大 Prompt

每个 Agent 只负责一类决策，状态在节点间显式传递。QA 失败时只回到 codegen，避免从需求解析重新开始；同时每一步都可以单独测试、替换或接入人工审核。

### RAG 如何真正参与生成

规划 Agent 先选择组件名，Component Agent 再用语义召回、玩法亲和度和冲突规则完成排序。Codegen 只接收命中的组件片段，而不是把整个知识库塞进 prompt；这样组件复用边界清晰，也方便解释每次命中原因。



## Extending the system

1. 在 `src/templates/` 新增一个玩法模板。
2. 在 `components/library.yaml` 注册玩法和可选组件。
3. 给新玩法添加一个 `examples/*.txt` brief。
4. 在 `tests/self_test.py` 增加解析、规划、渲染和 QA 断言。

编排图不需要为每个新模板增加分支：模板选择、组件召回和渲染通过状态与知识库连接。

## License

MIT，见 [LICENSE](LICENSE)。
