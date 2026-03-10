import logging
import uuid
from datetime import datetime
from typing import Any

from app.schemas.langgraph_data import LangGraphState
from app.schemas.session import ChunkSchema, FileSchema, MessageSchema, RequestSchema, SessionSchema, SummarySchema
from app.tasks.lib_justtype.common.just_historymanager_v2 import JustHistoryManager
import asyncio

logger = logging.getLogger(__name__)


class JustMessage:
    def __init__(self, stat: LangGraphState):
        self.stat = stat
        self.just_history_manager = JustHistoryManager(stat)
    
    def get_relevant_history(self):
        try:
            question = self.get_question()
            history_str = self.just_history_manager.get_relevant_history(question, keep_recent_turns = 1, max_tokens = 8192)
            return history_str
        except:
            return ""

    @staticmethod
    def create_message_id():
        return "MS_" + datetime.today().strftime("%m%d%f")[:9] + str(uuid.uuid4())[:8]

    @staticmethod
    def create_chunk_id():
        return "CK_" + datetime.today().strftime("%m%d%f")[:9] + str(uuid.uuid4())[:8]

    def get_question(self) -> str | None:
        if self.stat:
            last_message = self.get_last_message(["question", "llm_question", "multi_question"])
            if last_message is None:
                return None
            return last_message.content
        else:
            return None

    def get_question_type(self) -> str | None:
        if self.stat:
            last_message = self.get_last_message(["question", "llm_question", "multi_question"])
            if last_message is None:
                return None
            return last_message.type
        else:
            return None

    def append_question(self, q_type: str = "empty_question", message: str = None):
        if message is None:
            message = ""

        new_message = MessageSchema(
            id=self.create_message_id(),
            type=q_type,
            content=message,
            percentage=100,  # -1로 넣으면, Client가 Fail로 인식함.
            created_at=datetime.now(),
        )
        self.append_message(new_message)

    def append_answer(self, message: str, percentage=100, chunks=None, files=None):
        if message is None:
            message = ""

        question_type = self.get_question_type()
        if question_type == "llm_question":
            answer_type = "llm_answer"
        else:
            answer_type = "answer"  # multi_question, question은 그냥 answer로 답한다.

        new_message = MessageSchema(
            id=self.create_message_id(),
            type=answer_type,
            content=message,
            percentage=percentage,  # -1로 넣으면, Client가 Fail로 인식함.
            created_at=datetime.now(),
            chunks=chunks,
            files=files,
        )
        self.append_message(new_message)
        self.stat["client_info"].res_data.percentage = percentage

    def update_answer(self, message=None, percentage=None, chunks=None, pure_message=None, files=None, summaries=None, button_info=None, extra_data=None):
        if not isinstance(message, str):
            message = ""

        last_message = self.get_last_message(["answer", "llm_answer"])
        if last_message is None:
            self.append_answer(message, percentage, chunks)
        else:
            if message is not None:
                last_message.content = message
            if percentage is not None:
                last_message.percentage = percentage
            if chunks is not None:
                last_message.chunks = chunks
            if pure_message is not None:
                last_message.pure_content = pure_message
            if files is not None:
                last_message.files = files
            if summaries is not None:
                last_message.summaries = summaries
            if button_info is not None:
                last_message.button_info = button_info
            if extra_data is not None:
                last_message.extra_data = extra_data
                
            # last_message.isStreamLoading = False
            # last_message.isStreaming = False
            last_message.created_at = datetime.now()

        if percentage:
            self.stat["client_info"].res_data.percentage = percentage

    def get_chunks(self) -> list[ChunkSchema] | None:
        last_message = self.get_last_message(["answer", "llm_answer"])
        if last_message is None:
            return None
        return last_message.chunks

    # def get_chunk_list(self) -> list[ChunkSchema] | None:
    #     last_message = self.get_last_message("answer")
    #     if last_message is None:
    #         return None
    #     return last_message.chunk_list

    def get_files(self) -> list[FileSchema] | None:
        last_message = self.get_last_message(["question", "llm_question", "multi_question"])
        if last_message is None:
            return None
        return last_message.files

    def get_summaries(self) -> list[SummarySchema] | None:
        last_message = self.get_last_message(["answer", "llm_answer"])
        if last_message is None:
            return None
        return last_message.summaries

    def get_extra_data(self) -> dict[str, Any] | None:
        last_message = self.get_penultimate_message(["answer", "llm_answer"])
        if last_message is None:
            return None
        return last_message.extra_data

    def get_cur_extra_data(self) -> dict[str, Any] | None:
        last_message = self.get_last_message(["answer", "llm_answer"])
        if last_message is None:
            return None
        return last_message.extra_data

    def get_question_message(self) -> MessageSchema | None:
        return self.get_last_message(["question", "llm_question", "multi_question"])

    def get_answer_message(self) -> MessageSchema | None:
        return self.get_last_message(["answer", "llm_answer"])

    def append_message(self, new_message: MessageSchema):
        session_data = self.stat["client_info"].res_data
        session_data.messages.append(new_message)
        return True

    def update_message(self, new_message: MessageSchema):
        """
        기존 메시지를 업데이트하거나 새로 추가
        - new_message.id가 존재하면 기존 메시지를 찾아 삭제한 후 새 메시지를 추가
        - 기존 메시지를 찾지 못하면 새로운 메시지만 추가
        """
        session_data = self.stat["client_info"].res_data
        if new_message.id:
            for index, msg in enumerate(session_data.messages):
                if msg.id == new_message.id:
                    del session_data.messages[index]
                    break  # 메시지는 유일하므로 첫 번째 매칭 후 종료

        # 새로운 메시지 추가
        session_data.messages.append(new_message)
        return True

    def delete_message(self, start_idx: int, end_idx: int = None) -> int:
        """
        인덱스 범위로 메시지 삭제

        Args:
            start_idx (int): 시작 인덱스 (포함)
            end_idx (int, optional): 끝 인덱스 (포함되지 않음). None이면 start_idx 하나만 삭제

        Returns:
            int: 삭제된 메시지 개수
        """
        session_data = self.stat["client_info"].res_data
        if not session_data.messages:
            return 0

        total_messages = len(session_data.messages)

        # 음수 인덱스 처리
        if start_idx < 0:
            start_idx = max(0, total_messages + start_idx)
        else:
            start_idx = min(start_idx, total_messages)

        # end_idx가 None이면 단일 요소 삭제
        if end_idx is None:
            if 0 <= start_idx < total_messages:
                del session_data.messages[start_idx]
                return 1
            else:
                return 0

        # end_idx 처리 - 범위를 벗어나면 최대값으로 제한
        if end_idx < 0:
            end_idx = max(0, total_messages + end_idx)
        else:
            end_idx = min(end_idx, total_messages)  # 최대값으로 제한

        # start가 end보다 크거나 같으면 삭제할 것이 없음
        if start_idx >= end_idx:
            return 0

        # 삭제할 메시지 개수 계산
        delete_count = end_idx - start_idx

        # 뒤에서부터 삭제 (인덱스 변화 방지)
        for i in range(end_idx - 1, start_idx - 1, -1):
            if i < len(session_data.messages):
                del session_data.messages[i]

        return delete_count

    def get_last_message(self, message_type: str | list[str] = None) -> MessageSchema | None:
        session_data = self.stat["client_info"].res_data
        if session_data.messages is None:
            return None

        if message_type is None:
            return session_data.messages[-1]

        # 문자열이면 리스트로 변환
        if isinstance(message_type, str):
            message_type = [message_type]

        last_message = next((msg for msg in reversed(session_data.messages) if msg.type in message_type), None)
        return last_message

    def get_penultimate_message(self, message_type: str | list[str] = None) -> MessageSchema | None:
        session_data = self.stat["client_info"].res_data
        if session_data.messages is None or len(session_data.messages) < 2:
            return None

        if message_type is None:
            return session_data.messages[-2]

        # 문자열이면 리스트로 변환
        if isinstance(message_type, str):
            message_type = [message_type]

        # 마지막 메시지를 제외하고 역순 탐색
        reversed_messages = reversed(session_data.messages[:-1])
        penultimate_message = next((msg for msg in reversed_messages if msg.type in message_type), None)

        return penultimate_message

    def get_history_str(self):
        """
        QNA 형식의 문자열을 생성하는 함수
        - 최근 2 메시지는 방금 질문한 내용과, 응답할 내용이므로 제외합니다.
        """
        session_data = self.stat["client_info"].res_data
        if not session_data.messages or len(session_data.messages) < 3:
            return ""

        qna_list = []

        for msg in session_data.messages[:-2]:  # 마지막 두 개의 메시지(현재의 질문/응답) 제외
            # for msg in session_data.messages:  # 마지막 두 개의 메시지(현재의 질문/응답) 제외
            if msg.type == "llm_question" or msg.type == "question":
                qna_list.append(f"Q : {msg.content}")
            elif msg.type == "answer" or msg.type == "llm_answer":
                if msg.pure_content and len(msg.pure_content) > 0:
                    qna_list.append(f"A : {msg.pure_content}")  # 응답은 pure_content
                else:
                    qna_list.append(f"A : {msg.content}")       # pure_content없어서 content에서 가져옴.

        return "\n".join(qna_list)

    def get_history_msg_list(self) -> list[dict]:
        """
        QNA 형식의 문자열을 생성하는 함수
        - 최근 2 메시지는 방금 질문한 내용과, 응답할 내용이므로 제외합니다.
        """
        session_data = self.stat["client_info"].res_data
        if not session_data.messages or len(session_data.messages) < 3:
            return ""

        qna_list = []

        for msg in session_data.messages[:-2]:  # 마지막 두 개의 메시지(현재의 질문/응답) 제외
            # for msg in session_data.messages:  # 마지막 두 개의 메시지(현재의 질문/응답) 제외
            if msg.type == "llm_question" or msg.type == "question":
                qna_list.append({"role": "user", "content": msg.content})
            else:
                if msg.pure_content and len(msg.pure_content) > 0:
                    qna_list.append({"role": "assistant", "content": msg.pure_content}) # 응답은 pure_content
                else:
                    qna_list.append({"role": "assistant", "content": msg.content}) # pure_content없어서 content에서 가져옴.

        return qna_list


    def get_history_messages(self) -> list[dict]:
        """
        대화 히스토리를 user/assistant 턴 리스트로 반환.
        [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
        - 최근 2 메시지(현재 질문/응답)는 제외합니다.
        """
        session_data = self.stat["client_info"].res_data
        if not session_data.messages or len(session_data.messages) < 3:
            return []

        turns = []
        for msg in session_data.messages[:-2]:
            if msg.type in ("llm_question", "question"):
                turns.append({"role": "user", "content": msg.content})
            elif msg.type in ("answer", "llm_answer"):
                content = msg.pure_content if msg.pure_content and len(msg.pure_content) > 0 else msg.content
                turns.append({"role": "assistant", "content": content})
        return turns

    def get_history_list(self) -> str | None:
        """
        QNA 형식의 문자열을 생성하는 함수
        - 최근 2 메시지는 방금 질문한 내용과, 응답할 내용이므로 제외합니다.
        """
        session_data = self.stat["client_info"].res_data
        if not session_data.messages or len(session_data.messages) < 3:
            return ""

        qna_list = []

        for msg in session_data.messages[:-2]:  # 마지막 두 개의 메시지(현재의 질문/응답) 제외
            # for msg in session_data.messages:  # 마지막 두 개의 메시지(현재의 질문/응답) 제외
            if msg.type == "llm_question" or msg.type == "question":
                qna_list.append(f"Q : {msg.content}")
            elif msg.type == "answer":
                if msg.pure_content and len(msg.pure_content) > 0:
                    qna_list.append(f"A : {msg.pure_content}")  # 응답은 pure_content
                else:
                    qna_list.append(f"A : {msg.content}")       # pure_content없어서 content에서 가져옴.

        return qna_list

    def get_question_history_str(self) -> str | None:
        """
        QNA 형식의 문자열을 생성하는 함수
        - 최근 2 메시지는 방금 질문한 내용과, 응답할 내용이므로 제외합니다.
        """
        session_data = self.stat["client_info"].res_data
        if not session_data.messages or len(session_data.messages) < 3:
            return ""

        qna_list = []

        for msg in session_data.messages[:-2]:  # 마지막 두 개의 메시지(현재의 질문/응답) 제외
            # logger.info(f"========내용 확인 history[][]======{msg.content}=======")
            # logger.info(f"========내용 확인 history[][]======{msg}=======")
            if msg.type == "llm_question":
                qna_list.append(f"Q : {msg.content}")

        return "\n".join(qna_list)

    def get_request_messages(self) -> list[MessageSchema] | None:
        if self.stat:
            return self.stat["client_info"].req_data.messages
        return None

    def get_response_messages(self) -> list[MessageSchema] | None:
        if self.stat:
            return self.stat["client_info"].res_data.messages
        return None

    def get_request_session(self) -> RequestSchema | None:
        if self.stat:
            return self.stat["client_info"].req_data
        return None

    def get_response_session(self) -> SessionSchema | None:
        if self.stat:
            return self.stat["client_info"].res_data
        return None

    def set_session_title(self, title: str):
        session_info: SessionSchema = self.stat["client_info"].res_data
        session_info.session_title = title
