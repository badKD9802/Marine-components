"""LangGraph StreamWriter 대체 — asyncio.Queue 기반 SSE 이벤트 변환."""
import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SSEWriter:
    """ReactAgent의 writer() 호출을 asyncio.Queue SSE 이벤트로 변환.

    ReactAgent가 보내는 형식들:
    1. str (JSON): '{"replace_chunk": true, "steps": [...]}' → progress 이벤트
    2. str (HTML): '```html\n<div>...</div>\n```' → html 이벤트
    3. str (텍스트): 'LLM 토큰' → token 이벤트
    4. dict: {"replace_chunk": [old_tag, new_tag]} → progress 이벤트
    5. dict: {"button_info": [...]} → buttons 이벤트
    """

    def __init__(self, queue: asyncio.Queue):
        self.queue = queue

    def __call__(self, data: Any):
        try:
            if isinstance(data, str):
                self._handle_string(data)
            elif isinstance(data, dict):
                self._handle_dict(data)
        except Exception as e:
            logger.warning(f"SSEWriter 처리 실패: {e}")

    def _handle_string(self, data: str):
        stripped = data.strip()

        # 1) JSON 문자열 → progress 이벤트 (make_agent_progress 결과)
        if stripped.startswith("{"):
            try:
                parsed = json.loads(stripped)
                if "steps" in parsed:
                    self.queue.put_nowait(("progress", {"steps": parsed["steps"]}))
                    return
            except (json.JSONDecodeError, KeyError):
                pass

        # 2) HTML 콘텐츠 (```html 코드블록 또는 <태그>)
        if "```html" in data:
            html = self._strip_code_fence(data)
            self.queue.put_nowait(("html", {"content": html}))
            return

        if stripped.startswith("<") and not stripped.startswith("<excel-data>"):
            self.queue.put_nowait(("html", {"content": stripped}))
            return

        # 3) <excel-data> 태그 → 테이블 HTML 변환
        if "<excel-data>" in data:
            html = self._convert_excel_data(data)
            self.queue.put_nowait(("html", {"content": html}))
            return

        # 4) 일반 텍스트 토큰
        self.queue.put_nowait(("token", {"content": data}))

    def _handle_dict(self, data: dict):
        # 1) replace_chunk 패턴 → progress 이벤트
        if "replace_chunk" in data:
            # {"replace_chunk": true, "steps": [...]} 형태
            if "steps" in data:
                self.queue.put_nowait(("progress", {"steps": data["steps"]}))
                return

            # {"replace_chunk": [old_tag_json, new_tag_json]} 형태
            rc = data["replace_chunk"]
            if isinstance(rc, list) and len(rc) == 2:
                new_tag = rc[1]
                try:
                    parsed = json.loads(new_tag) if isinstance(new_tag, str) else new_tag
                    steps = parsed.get("steps", [])
                    self.queue.put_nowait(("progress", {"steps": steps}))
                except (json.JSONDecodeError, KeyError, AttributeError):
                    self.queue.put_nowait(("progress", data))
                return

            # 기타 replace_chunk
            self.queue.put_nowait(("progress", data))
            return

        # 2) 버튼 정보
        if "button_info" in data:
            self.queue.put_nowait(("buttons", data["button_info"]))
            return

        # 3) 기타 dict는 무시 (LangGraphState 등)

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        """```html ... ``` 마크다운 코드펜스 제거."""
        lines = text.split("\n")
        result = []
        inside = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```html"):
                inside = True
                continue
            if inside and stripped == "```":
                inside = False
                continue
            if inside or (not stripped.startswith("```")):
                result.append(line)
        return "\n".join(result).strip()

    @staticmethod
    def _convert_excel_data(text: str) -> str:
        """<excel-data> JSON → HTML 테이블로 변환."""
        try:
            import re
            match = re.search(r"<excel-data>\s*(.*?)\s*</excel-data>", text, re.DOTALL)
            if not match:
                return text
            obj = json.loads(match.group(1))
            title = obj.get("title", "데이터")
            data = obj.get("data", [])

            if not data:
                return f"<p>{title}: 데이터 없음</p>"

            # 테이블 생성
            headers = list(data[0].keys()) if data else []
            rows_html = ""
            for row in data:
                cells = "".join(f"<td style='padding:6px 10px;border:1px solid #ddd;'>{row.get(h, '')}</td>" for h in headers)
                rows_html += f"<tr>{cells}</tr>"

            header_html = "".join(f"<th style='padding:6px 10px;border:1px solid #ddd;background:#f5f5f5;font-weight:600;'>{h}</th>" for h in headers)

            return f"""<div style="margin:8px 0;">
<p style="font-weight:600;margin-bottom:6px;">{title}</p>
<div style="overflow-x:auto;">
<table style="border-collapse:collapse;width:100%;font-size:13px;">
<thead><tr>{header_html}</tr></thead>
<tbody>{rows_html}</tbody>
</table></div></div>"""
        except Exception as e:
            logger.warning(f"Excel 데이터 변환 실패: {e}")
            return text

    def write_event(self, event_type: str, data: dict):
        """직접 이벤트 타입을 지정하여 전송."""
        self.queue.put_nowait((event_type, data))


def format_sse(event: str, data: dict) -> str:
    """SSE 포맷 문자열 생성."""
    json_str = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {json_str}\n\n"
