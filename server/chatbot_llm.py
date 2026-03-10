"""JustLLM 대체 — standalone OpenAI 클라이언트."""
import os
from openai import AsyncOpenAI


class LLMClient:
    """JustLLM과 동일한 인터페이스의 standalone OpenAI 클라이언트."""

    def __init__(
        self,
        api_key: str = None,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        base_url: str = None,
    ):
        self.client = AsyncOpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url,
        )
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        self.temperature = temperature
        self.max_tokens = max_tokens

    def _build_request_params(self, messages, stream=False, tools=None, tool_choice=None):
        """react_agent.py의 _call_llm()에서 호출하는 인터페이스."""
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": stream,
        }
        if tools:
            params["tools"] = tools
            if tool_choice:
                params["tool_choice"] = tool_choice
        return params
