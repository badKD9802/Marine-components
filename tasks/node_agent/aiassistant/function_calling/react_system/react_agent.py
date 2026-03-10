"""ReAct Pattern Agent using JustLLM."""

import json
import logging
from types import SimpleNamespace
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

from app.tasks.node_agent.aiassistant.function_calling.react_system.prompts import get_system_prompt
from app.tasks.node_agent.prompts import make_agent_progress, make_agent_summary


# 도구 실행 중 문장형 문구
TOOL_SENTENCE_ACTIVE = {
    "get_schedule": "일정을 확인하고 있습니다",
    "create_schedule": "일정을 등록하고 있습니다",
    "update_schedule": "일정을 수정하고 있습니다",
    "delete_schedule": "일정을 삭제하고 있습니다",
    "get_meeting_room_list": "회의실 목록을 조회하고 있습니다",
    "reserve_meeting_room": "회의실을 예약하고 있습니다",
    "get_meeting_rooms": "회의실 현황을 확인하고 있습니다",
    "update_meeting_room": "회의실 예약을 수정하고 있습니다",
    "cancel_meeting_room": "회의실 예약을 취소하고 있습니다",
    "find_available_room": "빈 회의실을 찾고 있습니다",
    "get_all_meeting_rooms": "전체 회의실 현황을 조회하고 있습니다",
    "get_executive_schedule": "임원 일정을 확인하고 있습니다",
    "find_employee": "직원 정보를 검색하고 있습니다",
    "get_approval_form": "결재 양식을 조회하고 있습니다",
    "get_my_approvals": "결재 현황을 확인하고 있습니다",
    "approve_document": "문서를 승인하고 있습니다",
    "reject_document": "문서를 반려하고 있습니다",
    "draft_email": "이메일 초안을 작성하고 있습니다",
    "draft_document": "문서 초안을 작성하고 있습니다",
    "review_document": "문서를 검수하고 있습니다",
    "search_knowledge_base": "사내 지식베이스를 검색하고 있습니다",
    "translate_text": "번역하고 있습니다",
    "format_schedule_as_calendar": "일정 캘린더를 생성하고 있습니다",
    "format_schedule_as_table": "일정 표를 생성하고 있습니다",
    "format_meeting_rooms_as_calendar": "회의실 캘린더를 생성하고 있습니다",
    "format_meeting_rooms_as_table": "회의실 표를 생성하고 있습니다",
    "get_my_info": "내 정보를 불러오고 있습니다",
    "get_my_team": "팀원 목록을 불러오고 있습니다",
    "get_next_schedule": "다음 일정을 확인하고 있습니다",
    "get_weekly_summary": "주간 요약을 생성하고 있습니다",
    "format_data_as_table": "데이터를 표로 정리하고 있습니다",
    "format_data_as_excel": "엑셀 데이터를 생성하고 있습니다",
    "guide_document_draft": "문서 유형을 안내하고 있습니다",
}

# 도구 실행 완료 문장형 문구
TOOL_SENTENCE_DONE = {
    "get_schedule": "일정을 확인했습니다",
    "create_schedule": "일정을 등록했습니다",
    "update_schedule": "일정을 수정했습니다",
    "delete_schedule": "일정을 삭제했습니다",
    "get_meeting_room_list": "회의실 목록을 조회했습니다",
    "reserve_meeting_room": "회의실을 예약했습니다",
    "get_meeting_rooms": "회의실 현황을 확인했습니다",
    "update_meeting_room": "회의실 예약을 수정했습니다",
    "cancel_meeting_room": "회의실 예약을 취소했습니다",
    "find_available_room": "빈 회의실을 찾았습니다",
    "get_all_meeting_rooms": "전체 회의실 현황을 조회했습니다",
    "get_executive_schedule": "임원 일정을 확인했습니다",
    "find_employee": "직원 정보를 검색했습니다",
    "get_approval_form": "결재 양식을 조회했습니다",
    "get_my_approvals": "결재 현황을 확인했습니다",
    "approve_document": "문서를 승인했습니다",
    "reject_document": "문서를 반려했습니다",
    "draft_email": "이메일 초안을 작성했습니다",
    "draft_document": "문서 초안을 작성했습니다",
    "review_document": "문서 검수를 완료했습니다",
    "search_knowledge_base": "사내 지식베이스를 검색했습니다",
    "translate_text": "번역을 완료했습니다",
    "format_schedule_as_calendar": "일정 캘린더를 생성했습니다",
    "format_schedule_as_table": "일정 표를 생성했습니다",
    "format_meeting_rooms_as_calendar": "회의실 캘린더를 생성했습니다",
    "format_meeting_rooms_as_table": "회의실 표를 생성했습니다",
    "get_my_info": "내 정보를 불러왔습니다",
    "get_my_team": "팀원 목록을 불러왔습니다",
    "get_next_schedule": "다음 일정을 확인했습니다",
    "get_weekly_summary": "주간 요약을 생성했습니다",
    "format_data_as_table": "데이터를 표로 정리했습니다",
    "format_data_as_excel": "엑셀 데이터를 생성했습니다",
    "guide_document_draft": "문서 유형 안내를 완료했습니다",
}


class ReactAgent:
    """ReAct pattern agent using JustLLM."""

    def __init__(self, just_llm, tool_registry, tools, max_iterations=10, writer=None,
                 preferred_intent="", user_info: dict = None):
        """
        Initialize ReAct agent with JustLLM.

        Args:
            just_llm: JustLLM instance
            tool_registry: Tool registry instance
            tools: List of OpenAI tool schemas
            max_iterations: Max iterations to prevent infinite loops
            writer: LangGraph StreamWriter for SSE progress display (optional)
            preferred_intent: Fallback service hint (e.g. "calendar") for tool prioritization
            user_info: SLO 인증 사용자 정보 (user_nm, docdept_nm, emp_code 등)
        """
        self.llm = just_llm
        self.registry = tool_registry
        self.tools = tools
        self.max_iterations = max_iterations
        self.writer = writer
        self.preferred_intent = preferred_intent
        self.user_info = user_info
        self._current_tag = ""
        self._final_steps: List[Dict] = []
        self._html_blocks: List[str] = []  # html_content 누적 (DB 저장용)
        self._single_call_used: Dict[str, dict] = {}  # 1회 제한 도구: {func_name: {count, first_args}}
        self._blocked_call_ids: set = set()  # 차단된 tool_call ID (진행 UI 표시용)
        self._last_results: Dict[str, dict] = {}  # 도구별 마지막 결과 (자동 주입용)
        self._call_results: Dict[str, dict] = {}  # tool_call_id별 원본 결과 (preview용)
        self._summary_tag: str = ""  # finalize_progress 캐싱 (스트리밍 시 main.py에서 참조)

    def _update_progress(self, steps: List[Dict]):
        """진행 상태 업데이트 — replace_chunk 패턴으로 이전 태그 교체"""
        if not self.writer:
            return
        self._final_steps = steps
        # 내부 메타데이터 키(_로 시작)는 프론트에 전달하지 않음
        clean_steps = [{k: v for k, v in s.items() if not k.startswith("_")} for s in steps]
        new_tag = make_agent_progress(clean_steps)
        if self._current_tag:
            self.writer({"replace_chunk": [self._current_tag, new_tag]})
        else:
            self.writer(new_tag)
        self._current_tag = new_tag

    def finalize_progress(self) -> str:
        """진행 태그를 summary 태그로 교체 — 모든 active 상태를 completed로 전환 후 유지.
        Returns: summary_tag (DB 저장용). 이미 호출된 경우 캐싱된 값 반환.
        """
        if self._summary_tag:
            return self._summary_tag
        if not self.writer or not self._current_tag:
            return ""
        completed_steps = self._finalize_steps(self._final_steps)
        summary_tag = make_agent_summary(completed_steps)
        self.writer({"replace_chunk": [self._current_tag, summary_tag]})
        self._current_tag = ""
        self._summary_tag = summary_tag
        return summary_tag

    @staticmethod
    def _finalize_steps(steps: List[Dict]) -> List[Dict]:
        """모든 active 상태를 completed로 변환, 내부 메타데이터로 완료 문구 적용"""
        result = []
        for step in steps:
            new_step = {**step}
            if new_step.get("status") == "active":
                new_step["status"] = "completed"
                # _done_title이 있으면 완료 문구 사용 (마지막 도구 active 유지 케이스)
                done_title = new_step.pop("_done_title", None)
                if done_title:
                    new_step["title"] = done_title
                else:
                    title = new_step.get("title", "")
                    if title.endswith("..."):
                        new_step["title"] = title[:-3]
                preview = new_step.pop("_preview", None)
                if preview:
                    new_step.update(preview)
            # 내부 메타데이터 키 제거
            new_step = {k: v for k, v in new_step.items() if not k.startswith("_")}
            result.append(new_step)
        return result

    def _extract_preview(self, func_name: str, raw_result: Optional[dict] = None) -> dict:
        """조회 도구 결과에서 Claude 스타일 preview 데이터 추출.

        Returns:
            dict with optional keys: result_count (str), preview (list of {icon, text, sub})
        """
        result = raw_result or self._last_results.get(func_name)
        if not result or not isinstance(result, dict) or result.get("status") != "success":
            return {}

        extra = {}

        _MAX_PREVIEW = 4  # preview 최대 표시 수

        # ── 일정 조회 계열 ──
        if func_name in ("get_schedule", "get_next_schedule", "get_executive_schedule"):
            items = result.get("schedules", [])
            if items:
                extra["result_count"] = f"{len(items)}건의 일정"
                extra["preview"] = [
                    {"icon": "📅", "text": s.get("title", ""), "sub": s.get("start_date", "")[:16]}
                    for s in items[:_MAX_PREVIEW]
                ]

        # ── 회의실 목록 ──
        elif func_name == "get_meeting_room_list":
            rooms = result.get("rooms", [])
            if rooms:
                extra["result_count"] = f"{len(rooms)}개 회의실"
                extra["preview"] = [
                    {"icon": "🏢", "text": r.get("room_name", ""), "sub": r.get("location", "")}
                    for r in rooms[:_MAX_PREVIEW]
                ]

        # ── 회의실 현황/예약 조회 ──
        elif func_name in ("get_meeting_rooms", "get_all_meeting_rooms"):
            items = result.get("schedules", [])
            if items:
                extra["result_count"] = f"{len(items)}건의 예약"
                extra["preview"] = [
                    {"icon": "🏢", "text": s.get("title", ""), "sub": s.get("start_date", "")[:16]}
                    for s in items[:_MAX_PREVIEW]
                ]

        # ── 직원 검색 (도구에서 preview 필드 제공) ──
        elif func_name == "find_employee":
            count = result.get("total_count", 0)
            if count:
                extra["result_count"] = f"{count}명"
            if result.get("preview"):
                extra["preview"] = result["preview"][:6]

        # ── 내 정보 ──
        elif func_name == "get_my_info":
            extra["result_count"] = "조회 완료"

        # ── 팀원 목록 ──
        elif func_name == "get_my_team":
            count = result.get("total_count", 0)
            if count:
                extra["result_count"] = f"{count}명"
            if result.get("preview"):
                extra["preview"] = result["preview"][:6]

        return extra

    async def _call_llm(self, messages: List[Dict], *, allow_streaming: bool = False):
        """JustLLM을 사용하여 LLM 호출 (스트리밍 지원).

        Args:
            messages: 메시지 리스트
            allow_streaming: True이면 최종 답변(tool_calls 없는 응답)을 실시간 스트리밍

        Returns:
            (assistant_message, was_streamed)
            - assistant_message: SimpleNamespace(content, tool_calls) — OpenAI response와 동일 인터페이스
            - was_streamed: 최종 답변이 실시간 스트리밍 되었으면 True
        """
        has_system = any(m.get("role") == "system" for m in messages)
        if not has_system:
            all_messages = [{"role": "system", "content": get_system_prompt(
                preferred_intent=self.preferred_intent,
                user_info=self.user_info,
            )}] + messages
        else:
            all_messages = messages

        raw_data = self.llm._build_request_params(all_messages, stream=True)

        if self.tools:
            raw_data["tools"] = self.tools
            raw_data["tool_choice"] = "auto"

        stream = await self.llm.client.chat.completions.create(**raw_data)

        content = ""
        tool_calls_acc: Dict[int, dict] = {}  # index → {id, function: {name, arguments}}
        has_tool_calls = False
        streaming_started = False

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            # ── tool_calls 누적 ──
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                has_tool_calls = True
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {
                            "id": tc_delta.id or "",
                            "function": {"name": "", "arguments": ""},
                        }
                    entry = tool_calls_acc[idx]
                    if tc_delta.id:
                        entry["id"] = tc_delta.id
                    if hasattr(tc_delta, "function") and tc_delta.function:
                        if tc_delta.function.name:
                            entry["function"]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            entry["function"]["arguments"] += tc_delta.function.arguments

            # ── content 누적 + 실시간 스트리밍 ──
            if hasattr(delta, "content") and delta.content:
                content += delta.content
                if allow_streaming and not has_tool_calls and self.writer:
                    if not streaming_started:
                        # 첫 토큰 전에 progress → summary 전환
                        self.finalize_progress()
                        streaming_started = True
                    self.writer(delta.content)

        # ── 결과 조립 ──
        if has_tool_calls:
            tc_list = []
            for idx in sorted(tool_calls_acc.keys()):
                entry = tool_calls_acc[idx]
                tc_list.append(SimpleNamespace(
                    id=entry["id"],
                    function=SimpleNamespace(
                        name=entry["function"]["name"],
                        arguments=entry["function"]["arguments"],
                    ),
                ))
            return SimpleNamespace(content=content, tool_calls=tc_list), False

        return SimpleNamespace(content=content, tool_calls=None), streaming_started

    async def run(self, user_message: str, history: List[Dict] = None) -> dict:
        """
        Run the ReAct loop.

        Args:
            user_message: User's input message
            history: Optional conversation history

        Returns:
            dict: {
                "answer": Final answer text,
                "messages": New messages added to history (includes tool calls)
            }
        """
        messages = self._build_initial_messages(user_message, history)
        initial_length = len(history) if history else 0

        # 도구별 플랫 스텝 리스트 (Claude 스타일)
        tool_steps = []
        has_tool_calls = False
        executed_calls = set()  # (func_name, args_hash) 중복 방지

        logger.info("[ReactAgent] run() 시작 | 질문: %s | history 길이: %d | max_iterations: %d",
                    user_message[:80], len(history) if history else 0, self.max_iterations)

        for iteration in range(self.max_iterations):
            logger.info("[ReactAgent] --- 반복 %d/%d 시작 ---", iteration + 1, self.max_iterations)

            assistant_message, was_streamed = await self._call_llm(messages, allow_streaming=True)

            logger.info("[ReactAgent] LLM 응답 수신 | tool_calls 수: %d | content 길이: %d | streamed: %s",
                        len(assistant_message.tool_calls) if assistant_message.tool_calls else 0,
                        len(assistant_message.content or ""), was_streamed)

            # Add assistant's message to history
            message_dict = {
                "role": "assistant",
                "content": assistant_message.content or "",
            }

            # Include tool_calls if present
            if assistant_message.tool_calls:
                message_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in assistant_message.tool_calls
                ]

            messages.append(message_dict)

            # 최종 답변 (도구 호출 없음)
            if not assistant_message.tool_calls:
                logger.info("[ReactAgent] 반복 %d: 도구 호출 없음 → 최종 답변 반환 | has_tool_calls: %s | tool_steps 길이: %d | streamed: %s",
                            iteration + 1, has_tool_calls, len(tool_steps), was_streamed)
                logger.info("[ReactAgent] run() 정상 종료 (반복 %d)", iteration + 1)
                return {
                    "answer": assistant_message.content or "",
                    "html_blocks": self._html_blocks,
                    "messages": messages[initial_length:],
                    "streamed": was_streamed,
                }

            # 도구 호출 감지
            has_tool_calls = True
            current_tool_names = [tc.function.name for tc in assistant_message.tool_calls]
            logger.info("[ReactAgent] 반복 %d: 도구 호출 감지 → %s", iteration + 1, current_tool_names)

            # 이전 반복의 마지막 도구가 active 상태면 completed로 전환
            if tool_steps and tool_steps[-1].get("status") == "active":
                last = tool_steps[-1]
                last["status"] = "completed"
                done_title = last.pop("_done_title", None)
                if done_title:
                    last["title"] = done_title
                preview_data = last.pop("_preview", None)
                if preview_data:
                    last.update(preview_data)
                self._update_progress(tool_steps)

            # 중복 필터링
            filtered_calls, skipped_calls = self._filter_duplicate_calls(
                assistant_message.tool_calls, executed_calls
            )

            # 스킵된 도구에 dummy tool result 추가 (OpenAI API는 모든 tool_call에 대응하는 tool result 필요)
            for tc in skipped_calls:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps({"status": "skipped", "message": "이미 실행된 동일 요청입니다."}, ensure_ascii=False)
                })

            if not filtered_calls:
                # 모든 호출이 중복 → 강제 답변
                logger.warning("[ReactAgent] 반복 %d: 모든 도구 호출이 중복 → 강제 답변 생성", iteration + 1)
                break

            # Execute tool calls (도구별 순차 progress 업데이트)
            logger.info("[ReactAgent] 반복 %d: 도구 실행 시작 | 실행: %d, 스킵: %d", iteration + 1, len(filtered_calls), len(skipped_calls))
            tool_results = await self._execute_tool_calls(filtered_calls, executed_calls, tool_steps=tool_steps)
            logger.info("[ReactAgent] 반복 %d: 도구 실행 완료 | 결과 수: %d", iteration + 1, len(tool_results))

            # Add tool results to messages
            for tool_call_id, result in tool_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": result
                })

        # 최대 반복 도달 — 강제 최종 답변
        logger.warning("[ReactAgent] 최대 반복(%d) 도달 → 강제 최종 답변 생성", self.max_iterations)

        final_answer, was_streamed = await self._force_final_answer(messages)
        return {
            "answer": final_answer,
            "html_blocks": self._html_blocks,
            "messages": messages[initial_length:],
            "streamed": was_streamed,
        }

    @staticmethod
    def _build_dynamic_sentence(tc, sentence_map: dict, suffix: str = "") -> str:
        """도구 인자에서 핵심 값을 추출하여 동적 문구 생성.

        예: get_meeting_rooms(meetingroom="8층 영상회의실")
            → "8층 영상회의실 현황을 확인하고 있습니다"
        """
        name = tc.function.name
        base = sentence_map.get(name, f"{name} 실행 중")

        try:
            args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
        except (json.JSONDecodeError, TypeError):
            return base + suffix

        # 회의실 관련 도구 — meetingroom 인자로 동적 문구
        if name in ("get_meeting_rooms", "reserve_meeting_room", "update_meeting_room", "cancel_meeting_room"):
            room = args.get("meetingroom") or args.get("meetingroom_chg")
            if room:
                if name == "get_meeting_rooms":
                    return f"{room} 현황을 확인하고 있습니다" + suffix if "확인하고" in base else f"{room} 현황을 확인했습니다" + suffix
                elif name == "reserve_meeting_room":
                    return f"{room} 예약을 진행하고 있습니다" + suffix if "예약하고" in base else f"{room} 예약을 완료했습니다" + suffix
                elif name == "cancel_meeting_room":
                    return f"{room} 예약을 취소하고 있습니다" + suffix if "취소하고" in base else f"{room} 예약을 취소했습니다" + suffix

        # 직원 검색 — query 인자
        if name == "find_employee":
            query = args.get("query")
            if query:
                return f"'{query}' 직원 정보를 검색하고 있습니다" + suffix if "검색하고" in base else f"'{query}' 직원 정보를 검색했습니다" + suffix

        return base + suffix

    def _filter_duplicate_calls(self, tool_calls, executed_calls: set):
        """이미 실행한 (func_name, args_hash) 조합 필터링"""
        import hashlib
        filtered, skipped = [], []
        for tc in tool_calls:
            args_str = tc.function.arguments if isinstance(tc.function.arguments, str) \
                else json.dumps(tc.function.arguments, sort_keys=True)
            call_key = (tc.function.name, hashlib.md5(args_str.encode()).hexdigest())
            if call_key in executed_calls:
                logger.warning("[ReactAgent] 중복 도구 호출 차단: %s | args: %s", tc.function.name, args_str[:100])
                skipped.append(tc)
            else:
                filtered.append(tc)
        return filtered, skipped

    # run() 전체에서 1회만 실행 가능한 도구 목록
    _SINGLE_CALL_TOOLS = {"format_meeting_rooms_as_calendar"}

    # format 도구 자동 주입 매핑: {format_tool: (필수 파라미터, [소스 도구들])}
    _AUTO_INJECT_MAP = {
        "format_schedule_as_calendar":      ("schedules",    ["get_schedule"]),
        "format_schedule_as_table":         ("schedules",    ["get_schedule"]),
        "format_meeting_rooms_as_calendar": ("meeting_data", ["get_meeting_rooms", "get_all_meeting_rooms"]),
        "format_meeting_rooms_as_table":    ("meeting_data", ["get_meeting_rooms", "get_all_meeting_rooms"]),
    }

    async def _execute_tool_calls(self, tool_calls, executed_calls: set = None,
                                   tool_steps: list = None) -> List[tuple]:
        """
        Execute tool calls (async — delegates to async registry.dispatch).
        도구별 순차 progress 업데이트: active → 실행 → completed (마지막 도구는 active 유지).

        Args:
            tool_calls: List of tool call objects
            executed_calls: Set of already-executed call keys (for dedup)
            tool_steps: Progress step list (mutated in-place for per-tool updates)

        Returns:
            List of (tool_call_id, result_json_string) tuples
        """
        results = []
        total = len(tool_calls)

        for i, tc in enumerate(tool_calls):
            is_last = (i == total - 1)
            # executed_calls에 등록 (중복 방지용)
            if executed_calls is not None:
                import hashlib
                args_str = tc.function.arguments if isinstance(tc.function.arguments, str) \
                    else json.dumps(tc.function.arguments, sort_keys=True)
                call_key = (tc.function.name, hashlib.md5(args_str.encode()).hexdigest())
                executed_calls.add(call_key)

            logger.info("[ReactAgent] 도구 실행: %s | args: %s", tc.function.name, tc.function.arguments[:200] if isinstance(tc.function.arguments, str) else str(tc.function.arguments)[:200])

            # 1회 제한 도구 체크 (run() 전체에서 추적)
            func_name = tc.function.name
            if func_name in self._SINGLE_CALL_TOOLS:
                prev = self._single_call_used.get(func_name)
                if prev is not None:
                    # 이미 1회 실행됨 → 차단 (active 추가 없이 skip)
                    first_desc = prev.get("description", "")
                    try:
                        blocked_args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                        blocked_desc = blocked_args.get("meetingroom_name", "")
                        if not blocked_desc and isinstance(blocked_args.get("meeting_data"), dict):
                            blocked_desc = blocked_args["meeting_data"].get("room_info", {}).get("meetingroom_name", "")
                    except Exception:
                        blocked_desc = ""
                    blocked_desc = blocked_desc or "다른 회의실"
                    logger.warning("[ReactAgent] 1회 제한 도구 차단: %s (표시됨: %s, 차단됨: %s)", func_name, first_desc, blocked_desc)
                    blocked_result = {
                        "status": "blocked",
                        "message": (
                            f"[중요] '{blocked_desc}' 달력 생성이 차단되었습니다. 이 호출은 실행되지 않았습니다. "
                            f"현재 화면에는 '{first_desc}' 달력만 표시된 상태입니다. "
                            f"'{blocked_desc}' 달력은 표시되지 않았습니다. "
                            f"사용자에게 답변할 때: "
                            f"1) '{first_desc}' 달력만 보여드렸다고 말하세요 ('{blocked_desc}'은 포함하지 마세요). "
                            f"2) '{blocked_desc}'도 달력으로 보고 싶으시면 따로 요청해달라고 안내하세요. "
                            f"3) 또는 두 회의실을 한눈에 비교하려면 표 형식을 제안하세요."
                        ),
                    }
                    result_str = json.dumps(blocked_result, ensure_ascii=False)
                    results.append((tc.id, result_str))
                    self._blocked_call_ids.add(tc.id)
                    continue

            # ── 실행 전: 이 도구만 active 스텝 추가 ──
            if tool_steps is not None:
                sentence = self._build_dynamic_sentence(tc, TOOL_SENTENCE_ACTIVE, suffix="...")
                tool_steps.append({"title": sentence, "status": "active"})
                self._update_progress(tool_steps)

            try:
                # Parse arguments
                if isinstance(tc.function.arguments, str):
                    args = json.loads(tc.function.arguments)
                else:
                    args = tc.function.arguments

                # format 도구 자동 주입: 필수 파라미터가 비어있으면 이전 도구 결과에서 자동 주입
                if func_name in self._AUTO_INJECT_MAP:
                    param_name, source_tools = self._AUTO_INJECT_MAP[func_name]
                    if not args.get(param_name):
                        for src in source_tools:
                            if src in self._last_results:
                                args[param_name] = self._last_results[src]
                                logger.info("[ReactAgent] 자동 주입: %s ← %s 결과", param_name, src)
                                break

                # 1회 제한 도구: 첫 호출 기록
                if func_name in self._SINGLE_CALL_TOOLS:
                    desc = args.get("meetingroom_name", "")
                    if not desc and isinstance(args.get("meeting_data"), dict):
                        room_info = args["meeting_data"].get("room_info", {})
                        desc = room_info.get("meetingroom_name", "")
                    self._single_call_used[func_name] = {"description": desc or "회의실"}

                # Dispatch to tool registry (async)
                result = await self.registry.dispatch(tc.function.name, args)
                if isinstance(result, dict):
                    self._call_results[tc.id] = result
                result_summary = str(result)[:300] if result else "None"
                logger.info("[ReactAgent] 도구 결과: %s → %s", tc.function.name, result_summary)

                if isinstance(result, dict) and result.get("status") == "success":
                    self._last_results[func_name] = result

                # HTML 직접 렌더링 처리
                if isinstance(result, dict) and "html_content" in result:
                    hc = result["html_content"]
                    if "<excel-data>" in hc:
                        html_block = f"\n{hc}\n"
                    else:
                        html_block = f"\n```html\n{hc}\n```\n"
                    logger.info("[ReactAgent] html_content 감지 → 스트림에 직접 출력 | 크기: %d bytes", len(result["html_content"]))
                    if self.writer:
                        self.writer(html_block)
                    self._html_blocks.append(html_block)
                    llm_result = {
                        "status": "success",
                        "message": "HTML로 화면에 표시 완료. 아래 data는 후속 질문 참조용이며, 사용자에게 다시 나열하지 마세요.",
                    }
                    if "text_summary" in result:
                        llm_result["data"] = result["text_summary"]
                    result = llm_result

                result_str = json.dumps(result, ensure_ascii=False)

            except Exception as e:
                logger.exception("[ReactAgent] 도구 실행 오류: %s | %s", tc.function.name, str(e))
                result_str = json.dumps({
                    "status": "error",
                    "message": f"함수 실행 중 오류 발생: {str(e)}"
                }, ensure_ascii=False)

            results.append((tc.id, result_str))

            # ── 실행 후: 스텝 업데이트 ──
            if tool_steps is not None:
                if is_last:
                    # 마지막 도구: active 유지 (LLM 답변 생성 대기 역할)
                    # → 다음 반복 시작 또는 finalize_progress()에서 completed 전환
                    sentence_done = self._build_dynamic_sentence(tc, TOOL_SENTENCE_DONE)
                    preview = self._extract_preview(func_name, self._call_results.get(tc.id))
                    tool_steps[-1]["_done_title"] = sentence_done
                    tool_steps[-1]["_preview"] = preview
                else:
                    # 중간 도구: completed로 즉시 전환
                    sentence_done = self._build_dynamic_sentence(tc, TOOL_SENTENCE_DONE)
                    step = {"title": sentence_done, "status": "completed"}
                    preview = self._extract_preview(func_name, self._call_results.get(tc.id))
                    step.update(preview)
                    tool_steps[-1] = step
                    self._update_progress(tool_steps)

        return results

    async def _force_final_answer(self, messages) -> tuple:
        """
        Force LLM to generate final answer when max iterations reached.

        Returns:
            (answer_text, was_streamed)
        """
        messages.append({
            "role": "user",
            "content": "지금까지 수집한 정보를 바탕으로 최종 답변을 생성해주세요."
        })

        assistant_message, was_streamed = await self._call_llm(messages, allow_streaming=True)
        return assistant_message.content or "답변을 생성할 수 없습니다.", was_streamed

    def _build_initial_messages(self, user_message: str, history: List[Dict] = None) -> List[Dict]:
        """
        Build initial message list.

        Args:
            user_message: Current user message
            history: Previous conversation history

        Returns:
            List of message dicts
        """
        messages = []

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        return messages
