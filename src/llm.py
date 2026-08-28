# -*- coding: utf-8 -*-
"""LLM 客户端封装：OpenAI 兼容协议，支持 mock 模式与 JSON 输出。"""

import json
import os
import re
from typing import Any, Dict


class LLMClient:
    """统一的大模型调用入口。

    - mock=True 时不发起任何网络请求（离线评审/自测用）。
    - 支持 OpenAI 及任意 OpenAI 兼容服务（DeepSeek、Kimi、通义等），
      通过环境变量 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 配置。
    """

    def __init__(self, mock: bool = False):
        self.mock = mock
        self.model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        self._client = None
        if not mock:
            api_key = os.environ.get("LLM_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "live 模式需要设置 LLM_API_KEY；离线演示请传入 --mock。"
                )
            from openai import OpenAI  # 延迟导入，mock 模式不强依赖
            self._client = OpenAI(
                api_key=api_key,
                base_url=os.environ.get("LLM_BASE_URL") or None,
                timeout=float(os.environ.get("LLM_TIMEOUT_SECONDS", "60")),
                max_retries=2,
            )

    def chat(self, system: str, user: str, temperature: float = 0.4, max_tokens: int = 4096) -> str:
        if self.mock:
            raise RuntimeError("mock 模式下不应调用 LLM，请检查节点是否提供了 mock 分支")
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content

    def chat_json(self, system: str, user: str, temperature: float = 0.2) -> dict:
        """要求模型输出 JSON，并做宽容解析（去 markdown 围栏）。"""
        text = self.chat(system + "\n只输出 JSON，不要输出任何其他文字。", user, temperature)
        return parse_json(text)


def parse_json(text: str) -> Dict[str, Any]:
    """从模型输出中提取第一个完整 JSON 对象，避免用贪婪正则误切嵌套 JSON。"""

    if not isinstance(text, str) or not text.strip():
        raise ValueError("模型没有返回 JSON 文本")

    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.I)
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", cleaned):
        try:
            value, _ = decoder.raw_decode(cleaned[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("模型返回内容中没有可解析的 JSON 对象")
