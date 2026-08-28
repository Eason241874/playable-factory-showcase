# -*- coding: utf-8 -*-
"""RAG 检索模块：面向组件库 / 玩法库 / 素材库的轻量检索（向量召回 + 规则重排）。

这套检索是按试玩广告生产的实际诉求调的，几个取舍记一下：

- 向量化首选 OpenAI 兼容 Embedding 接口（与 LLM 共用 base_url/key）；
  没配 key 或接口挂了就降级本地哈希词袋向量——离线评审环境必须能跑，
  这是硬约束，所以降级链上不做任何告警噪音，只在 provider 字段留痕迹。
- 纯向量召回对"组件"这种短文档效果一般（词面重叠少、语义近），
  所以召回之后再过一道业务规则重排：规划阶段点名的、玩法亲和的、
  历史 CTR 高的，依次加权。权重是过去几轮投放数据回扫拍出来的，
  别随手改，要改先跑一遍 tests/self_test.py 看排序有没有翻车。
- 语料不是只塞 display_name：tags、使用场景（when/scenario）、
  适配玩法全量进文档，词袋模型下字段越全，中英混合查询越稳。
"""

import hashlib
import math
import os
import re
from typing import Any, Dict, List, Optional

import yaml

LIB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "components", "library.yaml")


def load_library(path: str = LIB_PATH) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------- 向量化 ----------------

def _tokenize(text: str) -> List[str]:
    text = text.lower()
    # 英文/数字按词切；中文按单字 + 双字元组切。
    # 单字保证召回（"寻宝"查询能命中"宝藏"），双字压住误命中。
    en = re.findall(r"[a-z0-9_]+", text)
    zh = re.findall(r"[一-鿿]", text)
    bigrams = ["".join(zh[i:i + 2]) for i in range(len(zh) - 1)]
    return en + zh + bigrams


def _hash_embed(text: str, dim: int = 512) -> List[float]:
    """本地哈希词袋向量：无外部依赖，短文本组件库里效果够用。

    512 维是试出来的：256 维碰撞开始明显（"宝箱"和"宝石"会挤到同一个桶），
    1024 维对 20 来条语料纯属浪费内存。
    """
    vec = [0.0] * dim
    for tok in _tokenize(text):
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class Embedder:
    """Embedding 提供方封装：优先走 API，失败/未配置时本地降级。"""

    def __init__(self, mock: bool = False):
        self.mock = mock
        self.provider = "local-hash"
        self._client = None
        self._model = os.environ.get("LLM_EMBED_MODEL", "text-embedding-3-small")
        if not mock and os.environ.get("LLM_API_KEY"):
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=os.environ.get("LLM_API_KEY"),
                    base_url=os.environ.get("LLM_BASE_URL") or None,
                )
                self.provider = f"api:{self._model}"
            except Exception:
                self._client = None

    def embed(self, texts: List[str]) -> List[List[float]]:
        if self._client is not None:
            try:
                resp = self._client.embeddings.create(model=self._model, input=texts)
                return [d.embedding for d in resp.data]
            except Exception:
                pass  # 网络/配额异常时静默降级到本地向量
        return [_hash_embed(t) for t in texts]


def cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / na / nb


# ---------------- 检索器 ----------------

# 玩法 -> 天然适配的组件（投放数据回扫出来的共现先验，用于重排）
# 注意这只是"倾向"，不是白名单；规划阶段点名（boost）的权重远高于这里。
MECHANIC_AFFINITY = {
    "drag_merge": ["progress_bar", "hint_hand", "combo_text", "coin_counter"],
    "stack_build": ["hint_hand", "combo_text", "screen_shake"],
    "sort_puzzle": ["hint_hand", "progress_bar"],
    "tomb_explore": ["coin_counter", "task_goal", "hint_hand", "countdown", "screen_shake"],
    "balloon_rescue": ["hint_hand", "countdown", "screen_shake"],
}

# 重排权重：规划点名 > 玩法亲和 > 历史 CTR 先验。
# 0.5 / 0.15 / 0.10 这一组是按离线回放历史 brief 的命中率调的。
W_BOOST = 0.5
W_AFFINITY = 0.15
W_CTR = 0.10


class ComponentRetriever:
    """组件 / 玩法 / 素材三类条目的统一检索入口。

    - components：增强组件（倒计时、进度条那类），retrieve() 的主战场；
    - mechanics：玩法模板，retrieve_mechanics() 供规划阶段参考；
    - assets：美术资产（bundle 分组），assets_for() 按玩法拿整套素材。
    """

    def __init__(self, library: Optional[Dict[str, Any]] = None, mock: bool = False):
        self.library = library or load_library()
        self.components = self.library.get("components", [])
        self.mechanics = {m["name"]: m for m in self.library.get("mechanics", [])}
        self.assets = self.library.get("assets", [])
        self.embedder = Embedder(mock=mock)
        self._corpus_vecs: Optional[List[List[float]]] = None
        self._mech_vecs: Optional[Dict[str, List[float]]] = None

    # ---- 语料构建：字段给全是离线词袋质量的命脉 ----
    def _doc_text(self, c: Dict[str, Any]) -> str:
        return " ".join([
            c.get("display_name", ""),
            c.get("when", ""),
            c.get("scenario", ""),
            " ".join(c.get("tags", [])),
            " ".join(c.get("compatible_mechanics", [])),
            c.get("name", ""),
        ])

    def _mech_text(self, m: Dict[str, Any]) -> str:
        return " ".join([
            m.get("display_name", ""),
            m.get("description", ""),
            m.get("best_for", ""),
            " ".join(m.get("tags", [])),
            m.get("name", ""),
        ])

    def _ensure_index(self):
        if self._corpus_vecs is None:
            self._corpus_vecs = self.embedder.embed([self._doc_text(c) for c in self.components])

    def _ensure_mech_index(self):
        if self._mech_vecs is None:
            self._mech_vecs = {
                m["name"]: v
                for m, v in zip(self.library.get("mechanics", []),
                                self.embedder.embed([self._mech_text(m)
                                                     for m in self.library.get("mechanics", [])]))
            }

    # ---- 组件检索：向量召回 + 规则重排 ----
    def retrieve(self, query: str, top_k: int = 3, mechanic: Optional[str] = None,
                 boost: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """向量召回 + 规则重排。boost 为玩法规划阶段点名启用的组件名。"""
        self._ensure_index()
        qv = self.embedder.embed([query])[0]
        scored = []
        for c, cv in zip(self.components, self._corpus_vecs):
            s = cosine(qv, cv)
            if boost and c["name"] in boost:
                s += W_BOOST
            if mechanic and c["name"] in MECHANIC_AFFINITY.get(mechanic, []):
                s += W_AFFINITY
            # 历史 CTR 当先验：0.156 的组件大约 +0.016，只起微调作用，
            # 防止两个语义分相近时新组件把验证过的老组件挤下去
            s += W_CTR * float(c.get("ctr", 0) or 0)
            # 冲突组件降权：brief/plan 已点名了某组件时，它的冤家直接压到队尾
            if boost and set(c.get("conflicts", []) or []) & set(boost):
                s -= 0.4
            scored.append((s, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [dict(c, score=round(s, 4)) for s, c in scored[:top_k]]

    # ---- 玩法检索：给规划 Agent 的参考召回（不直接决定选谁）----
    def retrieve_mechanics(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        self._ensure_mech_index()
        qv = self.embedder.embed([query])[0]
        scored = sorted(
            ((cosine(qv, v), self.mechanics[name]) for name, v in self._mech_vecs.items()),
            key=lambda x: x[0], reverse=True,
        )
        return [dict(m, score=round(s, 4)) for s, m in scored[:top_k]]

    # ---- 素材打包：按玩法的 asset_bundle 取整套美术 ----
    def assets_for(self, mechanic: Optional[str]) -> Dict[str, str]:
        """返回 {资产名: 文件路径}；玩法没登记 bundle 时返回空表。"""
        mech = self.mechanics.get(mechanic or "", {})
        bundle = mech.get("asset_bundle")
        if not bundle:
            return {}
        base = os.path.join(os.path.dirname(LIB_PATH), "assets")
        out = {}
        for a in self.assets:
            if a.get("bundle") != bundle:
                continue
            path = os.path.join(base, a.get("file", ""))
            out[a["name"]] = path if a.get("file") and os.path.exists(path) else ""
        return out
