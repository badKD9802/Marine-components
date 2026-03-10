import logging
from typing import List

from openai import AsyncOpenAI

from app.schemas.langgraph_data import LangGraphState

logger = logging.getLogger(__name__)

import time
from dataclasses import dataclass, field

import numpy as np

from app.justtype.rag.just_model import Tokenizer
from app.tasks.lib_justtype.common.just_env import JustEnv
from app.tasks.lib_justtype.common.global_clients import get_async_openai_client


@dataclass
class Message:
    content: str
    type: str  # 'question' 또는 'answer'
    timestamp: float = field(default_factory=time.time)


class JustHistoryManager:
    def __init__(self, stat: LangGraphState):
        self.stat = stat
        just_env = JustEnv(stat)
        config = just_env.get_config("summary")
        retrieval_config = just_env.get_config("retrieval")
        self.embedding_config = retrieval_config.get("embedding_config", {})

        # 토큰나이저 로드
        # self.tokenizer_api = config["tokenizer_api"]
        self.tokenizer = Tokenizer(config["tokenizer"]).tokenizer
        # 임베딩 함수 초기화
        self.embedding_client = self._init_embedding_client()

    def _init_embedding_client(self):
        """전역 AsyncOpenAI 클라이언트 인스턴스를 가져옵니다."""
        # config를 전역 함수에 전달
        client = get_async_openai_client(self.embedding_config)
        # if client:
        #     logger.info("Successfully retrieved GLOBAL AsyncOpenAI client for JustHistoryManager.")
        # else:
        #     logger.error("Failed to retrieve GLOBAL AsyncOpenAI client for JustHistoryManager.")
        return client
    
        # openai_params = {}
        # if base := self.embedding_config.get("embedding_base_url"):
        #     openai_params["base_url"] = base
        # if key := self.embedding_config.get("embedding_api_key"):
        #     openai_params["api_key"] = key
        # try:
        #     client = AsyncOpenAI(**openai_params)
        #     logger.info("Embedding client initiaized.")
        #     return client
        # except Exception as e:
        #     logger.info(f"Error initializing embedding client: {e}")
        #     return None

    async def encode(self, texts: list[str]):
        """텍스트 리스트를 받아 임베딩 벡터 리스트 반환 (배치 처리)"""
        if not self.embedding_client:
            raise ConnectionError("Embedding client is not initialized.")

        # 유효한 텍스트만 필터링
        cleaned_texts = [str(t) for t in texts if isinstance(t, str) and t.strip() and t.lower() != "nan"]
        if not cleaned_texts:
            raise ValueError("No valid texts to embed")

        try:
            model_name = self.embedding_config.get("embedding_model", "pixie")
            logger.info(f"Encoding {len(cleaned_texts)} texts using model: {model_name}")
            start_time = time.time()

            result = await self.embedding_client.embeddings.create(input=cleaned_texts, model=model_name)
            logger.info(f"\n\nEmbedding completed in {time.time() - start_time:.4f}s\n\n")
            return [x.embedding for x in result.data]
        except Exception as e:
            logger.error(f"Error during embedding generation: {e}", exc_info=True)
            raise RuntimeError(f"Embedding failed: {e}")

    async def get_history_messages(self) -> List[Message] | None:
        """
        QNA 형식의 문자열을 생성하는 함수
        - 최근 2 메시지는 방금 질문한 내용과, 응답할 내용이므로 제외합니다.
        """
        session_data = self.stat["client_info"].res_data
        if not session_data.messages or len(session_data.messages) < 3:
            return ""

        qna_list = []
        idx = 1
        for msg in session_data.messages:
            if msg.type == "llm_question" or msg.type == "question":
                qna_list.append(Message(msg.content, f"Question {idx}"))
            elif msg.type == "answer" or msg.type == "llm_answer":
                if msg.pure_content and len(msg.pure_content) > 0:
                    qna_list.append(Message(msg.pure_content, f"Answer {idx}"))
                else:
                    qna_list.append(Message(msg.content, f"Answer {idx}"))
                idx += 1
        return qna_list

    async def get_relevant_history(self, question: str = None, keep_recent_turns: int = 1, max_tokens: int = 4096) -> str:
        current_question = question
        num_recent_messages = keep_recent_turns * 2
        messages = await self.get_history_messages()
        history_messages = messages[:-2] if len(messages) > 2 else []
        if not history_messages:
            return ""

        recent_messages = history_messages[-num_recent_messages:]
        past_messages = history_messages[:-num_recent_messages]

        final_messages = list(recent_messages)
        if past_messages:
            try:
                # 1. 과거 대화를 QA 쌍으로 재구성
                qa_pairs: List[Tuple[Message, Message]] = []
                combined_qa_texts: List[str] = []

                for i in range(0, len(past_messages) - 1, 2):
                    q_msg = past_messages[i]
                    a_msg = past_messages[i + 1]
                    if "Question" in q_msg.type and "Answer" in a_msg.type:
                        qa_pairs.append((q_msg, a_msg))
                        combined_qa_texts.append(f"{q_msg.type}: {q_msg.content}\n{a_msg.type}: {a_msg.content}")

                if qa_pairs:
                    # 2. 결합된 QA 텍스트로 임베딩 및 유사도 계산
                    all_texts_to_embed = [current_question] + combined_qa_texts
                    all_embeddings = np.array(await self.encode(all_texts_to_embed))

                    question_embeddings = all_embeddings[0]
                    past_qa_embeddings = all_embeddings[1:]

                    similarities = np.dot(np.array(past_qa_embeddings), np.array(question_embeddings).T).flatten()
                    relevant_qa_past = sorted(zip(similarities, qa_pairs), key=lambda x: x[0], reverse=True)

                    current_tokens = self._calculate_tokens(final_messages)
                    for sim, pair in relevant_qa_past:
                        q_msg, a_msg = pair
                        pair_str = self._build_string([q_msg, a_msg])
                        pair_tokens = len(self.tokenizer.encode(pair_str))
                        # pair_tokens = requests.post(f"{self.tokenizer_api}tokenize", json={"prompt": pair_str}).json()['count']


                        if current_tokens + pair_tokens <= max_tokens:
                            final_messages.extend([q_msg, a_msg])
                            current_tokens += pair_tokens
                        else:
                            break

            except Exception as e:
                logger.info(e)

        final_messages.sort(key=lambda x: x.timestamp)
        return self._build_string(final_messages)

    def _format_message(self, message: Message) -> str:
        if "Question" in message.type:
            return f"{message.type} : {message.content}"
        elif "Answer" in message.type:
            return f"{message.type} : {message.content}"
        return ""

    def _build_string(self, messages: List[Message]) -> str:
        return "\n".join([self._format_message(s) for s in messages])

    def _calculate_tokens(self, messages: List[Message]) -> int:
        history_str = self._build_string(messages)
        # return requests.post(f"{self.tokenizer_api}tokenize", json={"prompt": history_str}).json()['count']
        return len(self.tokenizer.encode(history_str))