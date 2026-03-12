"""Tool Registry - maps function names to implementations."""

import asyncio

from react_system.tools import (
    approval_tools,
    draft_tools,
    employee_tools,
    excel_tools,
    executive_tools,
    html_format_tools,
    meeting_tools,
    rag_tools,
    schedule_tools,
    summary_tools,
    translate_tools,
    user_tools,
)


class ToolRegistry:
    """Registry that maps function names to their implementations."""

    def __init__(self, auth=None):
        """Initialize the registry with all 27 tools (21 + 5 + 1 generic table).

        Args:
            auth: AuthContext instance (SLO 인증 결과). None이면 더미 데이터 모드.
        """
        self._auth = auth
        self._registry = {
            # Schedule tools (4)
            "get_schedule": schedule_tools.get_schedule,
            "create_schedule": schedule_tools.create_schedule,
            "update_schedule": schedule_tools.update_schedule,
            "delete_schedule": schedule_tools.delete_schedule,
            # Meeting room tools (5)
            "get_meeting_room_list": meeting_tools.get_meeting_room_list,
            "reserve_meeting_room": meeting_tools.reserve_meeting_room,
            "get_meeting_rooms": meeting_tools.get_meeting_rooms,
            "update_meeting_room": meeting_tools.update_meeting_room,
            "cancel_meeting_room": meeting_tools.cancel_meeting_room,
            # Executive tools (1)
            "get_executive_schedule": executive_tools.get_executive_schedule,
            # Employee tools (1)
            "find_employee": employee_tools.find_employee,
            # Approval tools (4)
            "get_approval_form": approval_tools.get_approval_form,
            "get_my_approvals": approval_tools.get_my_approvals,
            "approve_document": approval_tools.approve_document,
            "reject_document": approval_tools.reject_document,
            # Draft tools (4)
            "draft_email": draft_tools.draft_email,
            "draft_document": draft_tools.draft_document,
            "review_document": draft_tools.review_document,
            "guide_document_draft": draft_tools.guide_document_draft,
            # RAG tools (1) ⭐
            "search_knowledge_base": rag_tools.search_knowledge_base,
            # Translation tools (1) ⭐ NEW
            "translate_text": translate_tools.translate_text,
            # HTML Format tools (4) ⭐ NEW - 달력 + 표 형식
            "format_schedule_as_calendar": html_format_tools.format_schedule_as_calendar,
            "format_schedule_as_table": html_format_tools.format_schedule_as_table,
            "format_meeting_rooms_as_calendar": html_format_tools.format_meeting_rooms_as_calendar,
            "format_meeting_rooms_as_table": html_format_tools.format_meeting_rooms_as_table,
            # Generic table tool (1) ⭐ NEW - 범용 표
            "format_data_as_table": html_format_tools.format_data_as_table,
            # Excel tools (1) ⭐ NEW - 표 표시 + Excel 다운로드
            "format_data_as_excel": excel_tools.format_data_as_excel,
            # User tools (3) ⭐ NEW - 사용자 정보
            "get_my_info": user_tools.get_my_info,
            "get_my_team": user_tools.get_my_team,
            "get_next_schedule": user_tools.get_next_schedule,
            # Meeting enhancement (2) ⭐ NEW - 빈 회의실 찾기 + 전체 현황
            "find_available_room": meeting_tools.find_available_room,
            "get_all_meeting_rooms": meeting_tools.get_all_meeting_rooms,
            # Summary tools (1) ⚠️ OPTIONAL - 주간 요약 (필요시 주석 처리)
            "get_weekly_summary": summary_tools.get_weekly_summary,
        }

    async def dispatch(self, function_name, arguments):
        """
        Dispatch a function call to the appropriate implementation.
        Supports both sync and async tool functions.
        - async def → await directly
        - sync def → run in thread pool (asyncio.to_thread) to avoid blocking event loop

        Args:
            function_name: Name of the function to call
            arguments: Dict of arguments to pass to the function

        Returns:
            dict: Result from the function

        Raises:
            KeyError: If function_name is not registered
        """
        if function_name not in self._registry:
            raise KeyError(
                f"Function '{function_name}' not found in registry. "
                f"Available functions: {list(self._registry.keys())}"
            )

        func = self._registry[function_name]

        # auth가 있으면 _auth 파라미터로 자동 주입
        if self._auth:
            arguments = {**arguments, "_auth": self._auth}

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(**arguments)
            else:
                result = await asyncio.to_thread(func, **arguments)
            return result
        except TypeError as e:
            import traceback

            error_msg = f"""
❌ 도구 호출 실패 (파라미터 오류)

📋 함수: {function_name}
📋 에러: {str(e)}

🔍 전달된 파라미터:
{arguments}

📜 스택:
{traceback.format_exc()}
"""
            return {"status": "error", "message": error_msg}
        except Exception as e:
            import traceback

            error_msg = f"""
❌ 도구 실행 중 예상치 못한 에러

📋 함수: {function_name}
📋 에러: {str(e)}

🔍 전달된 파라미터:
{arguments}

📜 스택:
{traceback.format_exc()}
"""
            return {"status": "error", "message": error_msg}

    def list_functions(self):
        """
        Get list of all registered function names.

        Returns:
            list: List of function names
        """
        return list(self._registry.keys())

    def has_function(self, function_name):
        """
        Check if a function is registered.

        Args:
            function_name: Name to check

        Returns:
            bool: True if registered
        """
        return function_name in self._registry
