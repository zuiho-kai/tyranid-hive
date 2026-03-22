"""Anthropic LLM 客户端 —— 轻量封装，不依赖 anthropic SDK"""

import os
from typing import Optional

import httpx
from loguru import logger

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-4-6"


class AnthropicClient:
    """轻量级 Anthropic API 客户端（无第三方 SDK 依赖）"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.timeout = timeout

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def complete(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> str:
        """调用 Anthropic Messages API，返回纯文本内容"""
        if not self.api_key:
            raise RuntimeError("未设置 ANTHROPIC_API_KEY，无法调用 LLM")

        body: dict = {
            "model":      self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages":   messages,
        }
        if system:
            body["system"] = system

        logger.debug(f"[LLMClient] 调用 {self.model}，消息数={len(messages)}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                ANTHROPIC_API_URL,
                headers={
                    "x-api-key":         self.api_key,
                    "anthropic-version": ANTHROPIC_API_VERSION,
                    "content-type":      "application/json",
                },
                json=body,
            )
            resp.raise_for_status()

        data = resp.json()
        text = data["content"][0]["text"]
        logger.debug(f"[LLMClient] 响应 {len(text)} 字")
        return text
