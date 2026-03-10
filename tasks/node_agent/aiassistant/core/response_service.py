import ast
import json
from pathlib import Path

from langchain_core.prompts import load_prompt
from langgraph.types import StreamWriter

from app.tasks.lib_justtype.common.just_message import JustMessage, LangGraphState
from app.tasks.lib_justtype.rag.just_llm import JustLLM
from app.tasks.node_agent.aiassistant.core.base import BaseService
from app.tasks.node_agent.aiassistant.core.util import util


class ResponseService(BaseService):
    """응답 생성 서비스의 기본 클래스"""

    def __init__(self, prompt_filename: str = "parse.yaml"):
        super().__init__(prompt_filename)

    def _load_calendar_update_prompt(self):
        """calendar_update 전용 프롬프트 로드"""
        try:
            prompt_path = Path(__file__).parent.parent / "prompts" / "calendar_update.yaml"
            if prompt_path.exists():
                self.prompt_template = load_prompt(str(prompt_path))
        except Exception as e:
            print(f"calendar_update 프롬프트 로드 실패: {e}")

    def _load_meeting_update_prompt(self):
        """meeting_update 전용 프롬프트 로드"""
        try:
            prompt_path = Path(__file__).parent.parent / "prompts" / "meeting_update.yaml"
            if prompt_path.exists():
                self.prompt_template = load_prompt(str(prompt_path))
        except Exception as e:
            print(f"meeting_update 프롬프트 로드 실패: {e}")

    def get_parser_config(self, route: str) -> dict:
        """parser_config.json에서 해당 route의 설정을 가져오는 함수"""
        try:
            config_path = Path(__file__).parent.parent / "data" / "parser_config.json"
            with open(config_path, encoding="utf-8") as f:
                parser_dict = json.load(f)
            return parser_dict.get(route, {})
        except Exception as e:
            print(f"parser_config.json 로드 실패: {e}")
            return {}

    async def process(self, stat: LangGraphState, writer: StreamWriter) -> LangGraphState:
        just_msg = JustMessage(stat)
        ex_data = just_msg.get_extra_data()

        # calendar_update 또는 meeting_update인 경우에만 별도 프롬프트 로드
        original_route = ex_data.get("original_route", "") if ex_data else ""
        if original_route == "calendar_update":
            self._load_calendar_update_prompt()
        elif original_route == "meeting_update":
            self._load_meeting_update_prompt()

        if not self.prompt_template:
            return {"answer": "프롬프트 템플릿이 로드되지 않았습니다."}

        try:
            variables = self._extract_variables(stat)
            just_llm = JustLLM(stat, is_stream=True)

            if just_llm:
                send_message = await just_llm.make_send_msg(self.prompt_template.format(**variables))

                full_response = ""
                async for content in await just_llm.get_response(send_message):
                    if content:
                        full_response += content

                parsed = util.json_replace(full_response)
                answer = parsed

                # # 자연어 답변 추출 (JSON이면 "answer" 필드, 아니면 전체)
                # if isinstance(parsed, dict) and "answer" in parsed:
                #     answer = parsed["answer"]  # 자연어 답변
                # else:
                #     answer = parsed  # 전체 답변

                # parsed에서 key값 추출해서 curr_kv에 저장
                curr_kv = {k: v for k, v in parsed.items()} if isinstance(parsed, dict) else {}

                # variables["required"]가 curr_kv에 없으면 missing_keys에 추가
                required_keys_str = variables.get("required", "[]")
                try:
                    required_keys = ast.literal_eval(required_keys_str) if isinstance(required_keys_str, str) else required_keys_str
                except (ValueError, SyntaxError):
                    required_keys = []
                missing_keys = [key for key in required_keys if key not in curr_kv]

                # extra_data 구성
                extra_data = {"answer": answer, "curr_kv": curr_kv, "missing_keys": missing_keys, "variables": variables}

                # 기존 route 정보 보존
                if ex_data:
                    extra_data["route"] = ex_data.get("route", "")
                    extra_data["original_route"] = ex_data.get("original_route", "")

                just_msg.update_answer(answer, 100, extra_data=extra_data)

                return {"answer": answer, "curr_kv": curr_kv, "missing_keys": missing_keys, "variables": variables}
            else:
                response_message = "The information about the LLM in the [system config] is inaccurate"
                just_msg.update_answer(response_message, -1)
                return {"answer": response_message}

        except Exception as e:
            import traceback

            print(f"응답 생성 실패: {e}")
            print(f"상세 에러: {traceback.format_exc()}")
            error_msg = "응답 생성중 에러가 발생했습니다."
            just_msg.update_answer(error_msg, -1, extra_data={"answer": error_msg})
            return {"answer": error_msg}

    def _extract_variables(self, stat: LangGraphState) -> dict:
        """프롬프트에 필요한 변수들 자동 추출"""
        just_msg = JustMessage(stat)
        ex_data = just_msg.get_extra_data()

        required_vars = getattr(self.prompt_template, "input_variables", ["query"])
        variables = {}

        # 현재 route의 parser 설정 가져오기
        current_route = ex_data.get("original_route", ex_data.get("route", "")) if ex_data else ""
        parser_config = self.get_parser_config(current_route)

        # 프롬프트 필수 입력값들 추출
        for var in required_vars:
            if var == "query":
                variables[var] = just_msg.get_question() or ""
            elif var == "history":
                variables[var] = just_msg.get_history_str() or ""
            elif var == "additional_directions":
                variables[var] = parser_config.get("additional_directions", "")
            elif var == "required":
                variables[var] = str(parser_config.get("required", []))
            elif var == "required_1":
                variables[var] = str(parser_config.get("required_1", []))
            elif var == "required_2":
                variables[var] = str(parser_config.get("required_2", []))
            elif var == "required_3":
                variables[var] = str(parser_config.get("required_3", []))
            elif var == "optional":
                variables[var] = str(parser_config.get("optional", []))
            elif var == "optional_1":
                variables[var] = str(parser_config.get("optional_1", []))
            elif var == "optional_2":
                variables[var] = str(parser_config.get("optional_2", []))
            elif var == "missing_keys":
                # ex_data에서 missing_keys 가져오기
                missing_keys = ex_data.get("missing_keys", []) if ex_data else []
                variables[var] = str(missing_keys)
            else:
                # 기타 변수들
                default_values = {
                    "details": "구체적인 내용을 알려주세요.",
                    "prev_req_0": "",
                    "prev_req_1": "",
                    "prev_req_2": "",
                    "missing_keys": "[]",
                }
                # ex_data에서 먼저 찾고, 없으면 기본값 사용
                if ex_data and var in ex_data:
                    variables[var] = ex_data[var]
                else:
                    variables[var] = default_values.get(var, "")

        return variables
