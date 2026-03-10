"""LangGraph StreamWriter 대체 — asyncio.Queue 기반 SSE 이벤트 변환."""
import asyncio
import json
from typing import Any


class SSEWriter:
    """ReactAgent의 writer() 호출을 asyncio.Queue SSE 이벤트로 변환."""

    def __init__(self, queue: asyncio.Queue):
        self.queue = queue

    def __call__(self, data: Any):
        if isinstance(data, str):
            if "```html" in data or data.strip().startswith("<"):
                self.queue.put_nowait(("html", {"content": data}))
            else:
                self.queue.put_nowait(("token", {"content": data}))
        elif isinstance(data, dict):
            if "replace_chunk" in data:
                self.queue.put_nowait(("progress", data))
            elif "button_info" in data:
                self.queue.put_nowait(("buttons", data["button_info"]))
            # LangGraphState dict는 무시

    def write_event(self, event_type: str, data: dict):
        """직접 이벤트 타입을 지정하여 전송."""
        self.queue.put_nowait((event_type, data))


def format_sse(event: str, data: dict) -> str:
    """SSE 포맷 문자열 생성."""
    json_str = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {json_str}\n\n"
