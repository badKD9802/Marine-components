import json
from abc import ABC, abstractmethod
from pathlib import Path

from langchain_core.prompts import load_prompt
from langgraph.types import StreamWriter

from app.tasks.lib_justtype.common.just_message import JustMessage, LangGraphState


class BaseService(ABC):
    """모든 서비스 클래스의 추상 기본 클래스"""

    def __init__(self, prompt_filename: str):
        self.prompt_filename = prompt_filename
        self.prompt_template = self._load_prompt()

    def _load_prompt(self):
        """프롬프트 파일 로드"""
        try:
            prompt_path = Path(__file__).parent.parent / "prompts" / self.prompt_filename
            # with open(prompt_path, encoding="utf-8") as f:
            #     return load_prompt(f.read())
            return load_prompt(str(prompt_path), encoding="utf-8")
        except Exception as e:
            print(f"프롬프트 로드 실패 ({self.prompt_filename}): {e}")
            return None

    @abstractmethod
    async def process(self, stat: LangGraphState, writer: StreamWriter) -> LangGraphState:
        """서비스의 핵심 처리 로직 (각 서비스에서 구현)"""
        pass

    async def __call__(self, stat: LangGraphState, writer: StreamWriter) -> LangGraphState:
        result = await self.process(stat, writer)  # 이 부분에 await 추가했는지 확인

        # 기존 state의 모든 값을 보존하고, result로 업데이트
        # (external_data) 가 기준이 아니고 각 클래스 process의 반환값이 누적된 result가 기준)
        updated_state = {**stat, **result}

        # 포맷팅 처리
        if "answer" in updated_state:
            answer = updated_state.get("answer", "응답을 생성할 수 없습니다!")
            # answer가 딕셔너리인 경우 특정 형식으로 변환
            if isinstance(answer, dict):
                formatted_lines = []

                # 모든 키-값 쌍을 순회하면서 처리
                for key, value in answer.items():
                    if key == "start_dt" and value:
                        # ISO 형식을 일반 날짜 형식으로 변환
                        start_dt = value.replace("T", " ").replace("+09:00", "")
                        formatted_lines.append(f"START_DT : {start_dt}")
                    elif key == "end_dt" and value:
                        # ISO 형식을 일반 날짜 형식으로 변환
                        end_dt = value.replace("T", " ").replace("+09:00", "")
                        formatted_lines.append(f"END_DT : {end_dt}")
                    elif key == "select_dt" and value:
                        # ISO 형식을 일반 날짜 형식으로 변환
                        end_dt = value.replace("T", " ").replace("+09:00", "")
                        formatted_lines.append(f"SELECT_DT : {end_dt}")
                    elif key == "equipment_ids" and value:
                        equipment = value
                        if isinstance(equipment, list):
                            equipment = ", ".join(equipment)
                        formatted_lines.append(f"EQUIPMENT_IDS : {equipment}")
                    elif value:  # 다른 모든 키-값 쌍도 포함 (값이 있는 경우만)
                        formatted_lines.append(f"{key.upper()} : {value}")

                # Streamlit markdown을 위해 HTML <br> 태그 사용
                answer = "<br>".join(formatted_lines) if formatted_lines else json.dumps(answer, ensure_ascii=False, indent=2)
                updated_state["answer"] = answer

                just_msg = JustMessage(stat)
                ex_data = just_msg.get_extra_data()
                print(f"base_extra_data : {ex_data }")

        return updated_state
