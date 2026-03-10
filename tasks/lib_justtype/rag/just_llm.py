import base64
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from io import BytesIO
import re
from openai import AsyncOpenAI
from PIL import Image
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, create_model
from typing import Optional, List, Dict, Any, Type
from jinja2 import Environment, StrictUndefined, Undefined

from app.schemas.langgraph_data import LangGraphState
from app.tasks.lib_justtype.common.just_env import JustEnv
import json

from app.tasks.node_agent.nodes.response_css_style import *
from app.tasks.lib_justtype.common.just_message import JustMessage
from app.tasks.lib_justtype.common import util
from app.tasks.node_agent.prompts import (
    GENERATE_MULTI_QUERIES_SYSTEM_PROMPT,
    GENERATE_MULTI_QUERIES_USER_PROMPT,
    RELEVANCE_FILTER_SYSTEM_PROMPT,
    RELEVANCE_FILTER_USER_PROMPT,
    QUERY_REWRITE_SYSTEM_PROMPT,
    QUERY_REWRITE_USER_PROMPT,
    GUIDE_CLS_SYSTEM_PROMPT,
    GUIDE_CLS_USER_PROMPT,
)
import asyncio

logger = util.TimeCheckLogger(logging.getLogger(__name__), "==JUST_LLM==")


@dataclass
class MultiQueryResult:
    """generate_multi_queries 반환 객체. refined_question과 generated_queries를 분리하여 인덱스 오프셋 문제 방지."""

    refined_question: str
    generated_queries: list = field(default_factory=list)
    extracted_rule: str = ""
    query_term: dict = field(default_factory=dict)
    is_proper_request: bool = True
    session_title: str = ""
    is_multi_topic: bool = False
    topic_groups: list = field(default_factory=list)  # list[dict] — TopicGroup model_dump()
    shared_query_indices: list = field(default_factory=list)  # generated_queries 기준 0-based


class AbstractLLM(ABC):
    @abstractmethod
    async def make_send_msg(self, prompt_str):
        pass

    @abstractmethod
    async def get_response(self, data):
        pass

    @abstractmethod
    async def after_send(self, result, start_time):
        pass

    @abstractmethod
    async def after_send_stream(self, result, start_time):
        pass


def _clean_and_parse_json(raw_text):
    refined_text = raw_text.strip()
    match = re.search(r"```(json)?(.*)```", refined_text, re.DOTALL)
    if match:
        refined_text = match.group(2).strip()
    if not refined_text.startswith("{"):
        refined_text = "{" + refined_text
    if not refined_text.endswith("}"):
        refined_text += "}"
    return refined_text

def _enforce_strict_schema(schema: dict) -> dict:
    """
    OpenAI Structured Outputs 요구사항에 맞게 JSON Schema를 변환:
    1. 모든 object에 "additionalProperties": false 추가
    2. 모든 properties의 키를 "required"에 추가
    3. 중첩 object, $defs 내부까지 재귀 처리
    """
    if not isinstance(schema, dict):
        return schema

    # $defs 처리
    if "$defs" in schema:
        for def_name, def_schema in schema["$defs"].items():
            schema["$defs"][def_name] = _enforce_strict_schema(def_schema)

    # object 타입 처리
    if schema.get("type") == "object" and "properties" in schema:
        schema["additionalProperties"] = False
        schema["required"] = list(schema["properties"].keys())
        for prop_name, prop_schema in schema["properties"].items():
            schema["properties"][prop_name] = _enforce_strict_schema(prop_schema)

    # array의 items 처리
    if schema.get("type") == "array":
        if "items" not in schema or schema["items"] == {}:
            # 타입 미지정 list → 기본 string으로 보정
            schema["items"] = {"type": "string"}
        else:
            schema["items"] = _enforce_strict_schema(schema["items"])

    # anyOf, oneOf, allOf 처리
    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema:
            schema[key] = [_enforce_strict_schema(s) for s in schema[key]]

    return schema


class JustLLM(AbstractLLM):
    """
    지원 Provider (config의 "provider" 필드로 지정, 없으면 모델명으로 자동 추론):

      "openai"            - gpt-4o, gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, gpt-3.5-turbo 등
      "openai_reasoning"  - o1, o3, o3-mini, o3-pro, o4-mini 등
      "openai_hybrid"     - gpt-5, gpt-5.1, gpt-5.2 등 (reasoning + temperature 둘 다)
      "claude"            - Anthropic Claude (OpenAI SDK 호환)
      "gemini"            - Google Gemini (OpenAI SDK 호환)
      "custom"            - vLLM, gpt-oss 등 커스텀 서버
    """

    _MODEL_PROVIDER_RULES = [
        (("o1", "o3", "o4"),                                                        "openai_reasoning"),
        (("gpt-5",),                                                                "openai_hybrid"),
        (("gpt-4.1", "gpt-4o", "gpt-4-", "gpt-4 ", "gpt-3.5", "gpt-4.5", "gpt-4-turbo"), "openai"),
        (("claude",),                                                               "claude"),
        (("gemini",),                                                               "gemini"),
    ]

    def __init__(self, stat: LangGraphState, is_stream=False, llm_name=None):
        just_env = JustEnv(stat)
        just_msg = JustMessage(stat)
        self.question_type = just_msg.get_question_type()

        llm_config = just_env.get_config("llm")
        config = llm_config[llm_name] if llm_name else llm_config[llm_config["default_llm_name"]]

        self.base_url = config.get("base_url", None)
        self.api_key = config.get("api_key", "1234")
        self.model = config["model_name"]
        self.temperature = config.get("temperature", 0.1)
        self.max_tokens = config.get("max_tokens", None)
        self.top_p = config.get("top_p", None)
        self.stream = is_stream
        self.reasoning_effort = config.get("reasoning_effort", "low")
        self.provider = config.get("provider", self._infer_provider(self.model))

        self.client = AsyncOpenAI(
            base_url=self.base_url, api_key=self.api_key
        ) if self.base_url else AsyncOpenAI(api_key=self.api_key)

        logger.debug(f"[JustLLM] model={self.model}, provider={self.provider}")

    # ──────────────────────────────────────────────────────────
    # Provider 자동 추론
    # ──────────────────────────────────────────────────────────
    def _infer_provider(self, model: str) -> str:
        model_lower = model.lower()
        for prefixes, provider in self._MODEL_PROVIDER_RULES:
            if any(model_lower.startswith(p) for p in prefixes):
                return provider
        return "custom"

    # ──────────────────────────────────────────────────────────
    # 범용 파라미터 빌더
    # ──────────────────────────────────────────────────────────
    def _build_request_params(
        self,
        messages: list,
        *,
        temperature: float = None,
        max_tokens: int = None,
        top_p: float = None,
        frequency_penalty: float = None,
        repetition_penalty: float = None,
        skip_special_tokens: bool = None,
        reasoning_effort: str = None,
        response_format: dict = None,
        stream: bool = None,
    ) -> dict:
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        top_p = top_p if top_p is not None else self.top_p
        stream = stream if stream is not None else self.stream

        raw_data = {"model": self.model, "messages": messages, "stream": stream}
        provider = self.provider

        if provider == "openai":
            raw_data["temperature"] = temperature
            if top_p is not None:
                raw_data["top_p"] = top_p
            if max_tokens is not None:
                raw_data["max_tokens"] = max_tokens
            if frequency_penalty is not None:
                raw_data["frequency_penalty"] = frequency_penalty

        elif provider == "openai_reasoning":
            raw_data["reasoning_effort"] = reasoning_effort or self.reasoning_effort
            if max_tokens is not None:
                raw_data["max_completion_tokens"] = max_tokens

        elif provider == "openai_hybrid":
            raw_data["reasoning_effort"] = reasoning_effort or self.reasoning_effort
            if max_tokens is not None:
                raw_data["max_completion_tokens"] = max_tokens
            model_lower = self.model.lower()
            if "gpt-5." in model_lower or "gpt-5-mini" in model_lower or "gpt-5-nano" in model_lower:
                raw_data["temperature"] = temperature

        elif provider == "claude":
            raw_data["temperature"] = temperature
            if top_p is not None:
                raw_data["top_p"] = top_p
            raw_data["max_tokens"] = max_tokens if max_tokens is not None else 4096

        elif provider == "gemini":
            raw_data["temperature"] = temperature
            if top_p is not None:
                raw_data["top_p"] = top_p
            if max_tokens is not None:
                raw_data["max_tokens"] = max_tokens
            if frequency_penalty is not None:
                raw_data["frequency_penalty"] = frequency_penalty
            if reasoning_effort:
                raw_data["reasoning_effort"] = reasoning_effort

        else:  # custom (vLLM, gpt-oss 등)
            raw_data["temperature"] = temperature
            extra_body = {}
            if repetition_penalty is not None:
                extra_body["repetition_penalty"] = repetition_penalty
            if skip_special_tokens is not None:
                extra_body["skip_special_tokens"] = skip_special_tokens
            if frequency_penalty is not None:
                extra_body["frequency_penalty"] = frequency_penalty
            if top_p is not None:
                extra_body["top_p"] = top_p
            if max_tokens is not None:
                extra_body["max_tokens"] = max_tokens
            if extra_body:
                raw_data["extra_body"] = extra_body
            if "gpt" in self.model:
                raw_data["reasoning_effort"] = reasoning_effort or self.reasoning_effort

        if response_format is not None:
            raw_data["response_format"] = response_format

        return {k: v for k, v in raw_data.items() if v is not None}

    # ──────────────────────────────────────────────────────────
    # 구조화 LLM 호출 (공통 추출)
    # ──────────────────────────────────────────────────────────
    async def _structured_call(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[BaseModel],
        max_tokens: int = 1024,
        prefill: str = "{",
    ) -> dict:
        messages = [
            {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
            {"role": "user",   "content": [{"type": "text", "text": user_prompt}]},
            {"role": "assistant", "content": [{"type": "text", "text": prefill}]},
        ]

        # 스키마 생성 후 OpenAI strict 요구사항 적용
        raw_schema = response_model.model_json_schema()
        strict_schema = _enforce_strict_schema(raw_schema)

        response_format_dict = {
            "type": "json_schema",
            "json_schema": {
                "strict": True,
                "name": response_model.__name__,
                "schema": strict_schema,
            },
        }

        raw_data = self._build_request_params(
            messages,
            temperature=0.0,
            max_tokens=max_tokens,
            top_p=0.9,
            frequency_penalty=0.1,
            repetition_penalty=1.1,
            skip_special_tokens=True,
            reasoning_effort="low",
            response_format=response_format_dict,
            stream=False,
        )

        response = await self.client.chat.completions.create(**raw_data)
        content = response.choices[0].message.content
        final_json_str = _clean_and_parse_json(content)
        logger.debug(final_json_str)

        try:
            return response_model.model_validate_json(final_json_str).model_dump()
        except Exception:
            return json.loads(final_json_str)


    # ──────────────────────────────────────────────────────────
    # Jinja2 렌더링
    # ──────────────────────────────────────────────────────────
    def render_messages(self, yaml_data: dict, variables: dict, message_type: str, history_messages: list[dict] | None = None):
        """
        YAML 프롬프트 템플릿을 OpenAI messages 형식으로 렌더링.

        history_messages 파라미터가 주어지면:
          - YAML에서 {{ HISTORY }} placeholder가 포함된 메시지(기존에는 단일 assistant 메시지)를
            실제 user/assistant 교대 턴 배열로 교체한다.
          - 히스토리가 비어있으면 해당 메시지를 아예 생략한다.
          - 결과 예시:  system → user(Q1) → assistant(A1) → user(Q2) → assistant(A2) → user(현재질문)
        history_messages가 None이면:
          - 기존 방식 그대로. {{ HISTORY }} 변수에 문자열이 치환되어 단일 메시지로 렌더링.
        """
        env = Environment(undefined=StrictUndefined, autoescape=False)
        messages = []
        for m in yaml_data.get(message_type, []):
            content = m["content"]
            # history_messages가 주어지면 {{ HISTORY }} 메시지를 턴 배열로 교체
            if history_messages is not None and "HISTORY" in content:
                for turn in history_messages:
                    messages.append({"role": turn["role"], "content": [{"type": "text", "text": turn["content"]}]})
                continue  # 원래 HISTORY 메시지는 건너뜀
            if m.get("render", False):
                template = env.from_string(content.replace("{", "{{").replace("}", "}}"))
                content = template.render(**variables)
            messages.append({"role": m["role"], "content": [{"type": "text", "text": content}]})
        return messages

    def render_messages_v2(
        self,
        messages: list[dict],
        variables: dict,
        history_messages: list[dict] | None = None,
    ) -> list[dict]:
        """
        StructuredPrompt v2 messages 배열을 OpenAI messages 형식으로 렌더링.

        - messages_list role: history_messages 턴 배열로 확장 (없으면 생략)
        - render=True: Jinja2 직접 렌더 (v2 content는 이미 {{ }} 표준 형식)
        - render=False: content 그대로 사용
        """
        env = Environment(undefined=Undefined, autoescape=False)
        result = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")

            if role == "messages_list":
                if history_messages:
                    for turn in history_messages:
                        result.append({
                            "role": turn["role"],
                            "content": [{"type": "text", "text": turn["content"]}],
                        })
                continue

            if m.get("render", False):
                try:
                    content = env.from_string(content).render(**variables)
                except Exception:
                    pass

            result.append({"role": role, "content": [{"type": "text", "text": content}]})
        return result

    # ──────────────────────────────────────────────────────────
    # make_send_msg
    # ──────────────────────────────────────────────────────────
    async def make_send_msg(self, prompt_str="", messages=[], raw_data={}, image_data=None):
        if not messages:
            messages = []
            history_str = prompt_str.split("### 이전 대화:")
            if len(history_str) >= 2:
                prompt = history_str[0]
                history_question = history_str[1]
                split_prompt = history_question.split("### 현재 시간:")
                logger.info("000000")
                if len(split_prompt) >= 2:
                    history = "### 이전 대화:" + split_prompt[0]
                    question = "### 현재 시간:" + split_prompt[1]
                    messages.append({"role": "system", "content": [{"type": "text", "text": prompt}]})
                    messages.append({"role": "assistant", "content": [{"type": "text", "text": history}]})
                    messages.append({"role": "user", "content": [{"type": "text", "text": question}]})
                else:
                    messages.append({"role": "system", "content": [{"type": "text", "text": prompt}]})
                    messages.append({"role": "user", "content": [{"type": "text", "text": history_question}]})
            else:
                messages.append({"role": "user", "content": [{"type": "text", "text": prompt_str}]})
            if image_data:
                messages.append({"type": "image_url", "image_url": [{"url": f"data:image/png;base64,{image_data}"}]})

        if not raw_data:
            data = self._build_request_params(
                messages,
                repetition_penalty=1.1,
                skip_special_tokens=True,
                frequency_penalty=0.1,
            )
        else:
            data = {k: v for k, v in raw_data.items() if v is not None}
        return data

    # ──────────────────────────────────────────────────────────
    # get_response
    # ──────────────────────────────────────────────────────────
    async def get_response(self, data):
        start_time = time.time()
        max_retries = 3
        base_delay = 1.0
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = await self.client.chat.completions.create(**data)
                if self.stream:
                    return self.after_send_stream(response, start_time)
                else:
                    response_text = response.choices[0].message.content
                    await self.after_send(response_text, start_time)
                    return response_text
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    await asyncio.sleep(base_delay * (2 ** attempt))

        import traceback
        traceback.print_exc()
        return f"Error: LLM 호출 실패 (최대 {max_retries + 1}회 시도): {last_error}"

    # ──────────────────────────────────────────────────────────
    # Streaming
    # ──────────────────────────────────────────────────────────
    async def after_send_stream(self, response_stream, start_time):
        reasoning_started = False
        reasoning_done = False
        content_started = False
        iterator = response_stream.__aiter__()

        # ── TTFT / TPS 메트릭 추적 변수 ──
        first_token_time = None
        token_count = 0
        last_token_time = None

        while True:
            try:
                chunk = await iterator.__anext__()
            except StopAsyncIteration:
                break
            except Exception as e:
                if "Unknown role" in str(e) and "assistant<|channel|>analysis" in str(e):
                    print(f"[WARNING] 비표준 role 청크 스킵: {e}")
                    continue
                print(f"[ERROR] 스트림 읽기 중 치명적 에러: {e}")
                raise

            try:
                finish_reason = chunk.choices[0].finish_reason
                delta = chunk.choices[0].delta

                # 1) reasoning_content 처리 (CoT 모델만)
                if (
                    hasattr(delta, "reasoning_content")
                    and delta.reasoning_content is not None
                    and self.question_type == "question"
                ):
                    if not reasoning_started:
                        yield "<cot>"
                        reasoning_started = True
                    yield delta.reasoning_content

                # 2) content 처리
                if hasattr(delta, "content") and delta.content is not None:
                    if reasoning_started and not reasoning_done:
                        reasoning_done = True
                    if reasoning_started and not content_started:
                        yield "</cot>"
                        content_started = True

                    content = delta.content
                    content = re.sub(r"\u201c|\u201d", '"', content)
                    content = re.sub(r"\u2018|\u2019", "'", content)
                    content = re.sub(r"~", "&#126;", content)

                    # ── TTFT / TPS 추적 ──
                    token_count += 1
                    now = time.time()
                    if first_token_time is None:
                        first_token_time = now
                    last_token_time = now

                    yield content

                if finish_reason:
                    # ── finish_reason 시점에 메트릭 계산 및 저장 ──
                    if first_token_time is not None:
                        llm_ttft = round(first_token_time - start_time, 4)
                        generation_duration = (last_token_time - first_token_time) if last_token_time > first_token_time else 0
                        tps = round(token_count / generation_duration, 2) if generation_duration > 0 else 0.0
                        total_time = round(last_token_time - start_time, 4)

                        self.stream_metrics = {
                            "llm_ttft": llm_ttft,
                            "tps": tps,
                            "token_count": token_count,
                            "generation_time": round(generation_duration, 4),
                            "total_time": total_time,
                            "model": self.model,
                        }
                        logger.info(
                            f"[LLM Metrics] model={self.model} llm_ttft={llm_ttft}s TPS={tps} tokens={token_count} total={total_time}s"
                        )
                    else:
                        self.stream_metrics = None
                    yield "\n\n<end>"
            except Exception as chunk_error:
                logger.error(f"[LLM Error] {chunk_error}")
                logger.error(f"delta.role: {delta.role}")
                continue

    async def after_send(self, result, start_time):
        elapsed = round(time.time() - start_time, 3)
        logger.debug(f"response_text={result}")
        logger.debug(f"{self.model} elapse time :[{elapsed} sec]")
        return result + f"\n[elapsed time: {elapsed} sec]"

    def encode_image_to_base64(self, image_path: str) -> str:
        with Image.open(image_path) as img:
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode("utf-8")

    async def generate_text(self, prompt_text: str, image_path: str = None) -> str:
        content = []
        if image_path:
            image_base64 = self.encode_image_to_base64(image_path)
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}})
        content.append({"type": "text", "text": prompt_text})

        raw_data = self._build_request_params([{"role": "user", "content": content}], stream=False)
        response = await self.client.chat.completions.create(**raw_data)
        return response.choices[0].message.content

    # ──────────────────────────────────────────────────────────
    # 쿼리 리라이팅 (멀티턴 대명사/생략어 해소)
    # ──────────────────────────────────────────────────────────
    async def rewrite_query(self, question: str, chat_history: str,
                            previous_answer_summary: str = "") -> tuple[str, bool]:
        """대화 히스토리 기반 쿼리 리라이팅 + 검색 필요 여부 판단.

        Returns:
            tuple[str, bool]: (리라이팅된 질문, 검색 필요 여부)
            히스토리가 없거나 실패 시 (원본 질문, True) 반환.
        """
        if not chat_history or not chat_history.strip():
            return question, True

        class RewriteResponse(BaseModel):
            rewritten_query: str = Field(description="재작성된 완전한 질문")
            needs_retrieval: bool = Field(default=True, description="새로운 문서 검색 필요 여부")

        try:
            result = await self._structured_call(
                system_prompt=QUERY_REWRITE_SYSTEM_PROMPT,
                user_prompt=QUERY_REWRITE_USER_PROMPT.format(
                    chat_history=chat_history,
                    question=question,
                    previous_answer_summary=previous_answer_summary or "없음",
                ),
                response_model=RewriteResponse,
                max_tokens=512,
            )
            rewritten = result.get("rewritten_query", question)
            needs_retrieval = result.get("needs_retrieval", True)
            if rewritten and rewritten.strip():
                logger.debug(f"[Query Rewrite] '{question}' → '{rewritten}' (needs_retrieval={needs_retrieval})")
                return rewritten.strip(), needs_retrieval
            return question, True
        except Exception as e:
            logger.error(f"[Query Rewrite] Error: {e}")
            return question, True

    # ──────────────────────────────────────────────────────────
    # Multi-query 생성
    # ──────────────────────────────────────────────────────────
    async def generate_multi_queries(self, base_query: str, chat_history: str, sim_rule_title: str = "") -> MultiQueryResult:
        if not base_query or not isinstance(base_query, str):
            return MultiQueryResult(refined_question=base_query or "")

        extracted_rule = ""
        query_term = ""
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_year = datetime.now().strftime("%Y")
        current_yearmm = datetime.now().strftime("%Y-%m")
        last_year = (datetime.now() - timedelta(days=365)).strftime("%Y")

        # ── 스키마 정의 ──
        class ContextResolution(BaseModel):
            is_multi_turn: bool = Field(description="true 또는 false")
            reasoning: str = Field(description="왜 멀티턴(또는 싱글턴)으로 판단했는지에 대한 짧은 설명")
            refined_question: str = Field(description="재구성된 완전한 질문")

        class QueryTerm(BaseModel):
            reasoning: str = Field(description="문서 검색 기간에 대한 짧은 설명")
            start_ym: int = Field(default=202201, description="검색 시작 년월 yyyymm")
            end_ym: int = Field(description="검색 끝 년월 yyyymm")

        class TopicGroup(BaseModel):
            topic: str = Field(description="토픽 키워드 (식별/출력용)")
            query_indices: list[int] = Field(description="generated_queries에서 이 토픽에 해당하는 인덱스 (0-based)")
            validation_query: str = Field(description="리랭크/LLM검증에 사용할 세부 질문")

        class MultiQueryResponse(BaseModel):
            is_proper_request: bool = Field(description="올바른 쿼리인지 판단")
            context_resolution: ContextResolution
            query_term: QueryTerm
            generated_queries: list[str] = Field(description="토픽별 검색용 질문들 (2~4개). 멀티토픽이 아니면 1~3개")
            session_title: str = Field(default="", description="10자 이내 대화방 제목")
            is_multi_topic: bool = Field(default=False, description="질문에 2~3개 독립 토픽 포함 여부")
            topic_groups: list[TopicGroup] = Field(default=[], description="토픽별 쿼리 그룹")
            shared_query_indices: list[int] = Field(default=[], description="비교/공통 보조 쿼리 인덱스 (generated_queries 기준)")

        try:
            result = await self._structured_call(
                system_prompt=GENERATE_MULTI_QUERIES_SYSTEM_PROMPT.format(
                    current_date=current_date, current_year=current_year,
                    last_year=last_year, current_yearmm=current_yearmm,
                ),
                user_prompt=GENERATE_MULTI_QUERIES_USER_PROMPT.format(
                    current_date=current_date, chat_history=chat_history, base_query=base_query,
                ),
                response_model=MultiQueryResponse,
                max_tokens=2048,
            )

            context_resolution = result.get("context_resolution", {})
            query_term = result.get("query_term", {})
            generated_queries = result.get("generated_queries", [])
            extracted_rule = result.get("extracted_rule", "")
            is_proper_request = result.get("is_proper_request", True)
            session_title = result.get("session_title", "")
            is_multi_topic = result.get("is_multi_topic", False)
            topic_groups_raw = result.get("topic_groups", [])
            shared_query_indices = result.get("shared_query_indices", [])

            og_query = context_resolution.get("refined_question", base_query)

            # topic_groups: Pydantic model → dict 변환 (일관된 dict 사용)
            topic_groups = []
            for tg in topic_groups_raw:
                if isinstance(tg, dict):
                    topic_groups.append(tg)
                elif hasattr(tg, "model_dump"):
                    topic_groups.append(tg.model_dump())
                else:
                    topic_groups.append(dict(tg))

            logger.debug(
                f"[LLM Multi-query] Generated {len(generated_queries)} queries, "
                f"multi_topic={is_multi_topic}, topics={len(topic_groups)}"
            )

            return MultiQueryResult(
                refined_question=og_query,
                generated_queries=generated_queries,
                extracted_rule=extracted_rule,
                query_term=query_term if isinstance(query_term, dict) else {},
                is_proper_request=is_proper_request,
                session_title=session_title,
                is_multi_topic=is_multi_topic,
                topic_groups=topic_groups,
                shared_query_indices=shared_query_indices,
            )

        except Exception as e:
            logger.error(f"[LLM Multi-query] Error: {e}")
            return MultiQueryResult(refined_question=base_query)

    # ──────────────────────────────────────────────────────────
    # Relevance Filter
    # ──────────────────────────────────────────────────────────
    async def relevence_filter(
        self,
        base_query: str,
        refined_query: str,
        context: str,
        top_k: int = 5,
    ) -> tuple[list[int], list[int]]:
        class RelevanceResponse(BaseModel):
            reference_reasoning: str = Field(description="각 청크에 대한 평가 및 선택/탈락 이유를 한글로 간략히 서술")
            relevant_chunk_ids: list[int] = Field(description="참고용 ID 목록 (연관성 높은 순)")
            core_reasoning: str = Field(description="핵심 답변 참고 이유를 한글로 간략히 서술")
            core_chunk_ids: list[int] = Field(description="핵심 답변 ID 목록 (연관성 높은 순)")

        try:
            now_time = datetime.now().strftime("%Y-%m-%d")
            result = await self._structured_call(
                system_prompt=RELEVANCE_FILTER_SYSTEM_PROMPT,
                user_prompt=RELEVANCE_FILTER_USER_PROMPT.format(
                    now_time=now_time, base_query=base_query,
                    refined_query=refined_query, context=context,
                ),
                response_model=RelevanceResponse,
            )

            core_chunk_ids = result.get("core_chunk_ids", [])
            relevant_chunk_ids = result.get("relevant_chunk_ids", [])

            if not isinstance(core_chunk_ids, list):
                core_chunk_ids = []
            if not isinstance(relevant_chunk_ids, list):
                relevant_chunk_ids = []

            # core가 top_k 이상이면 relevant 불필요
            if len(core_chunk_ids) >= top_k:
                core_chunk_ids = core_chunk_ids[:top_k]
                relevant_chunk_ids = []
            else:
                # core에서 부족한 만큼만 relevant에서 보충
                remain = top_k - len(core_chunk_ids)
                core_set = set(core_chunk_ids)
                relevant_chunk_ids = [cid for cid in relevant_chunk_ids if cid not in core_set][:remain]

            logger.debug(f"[Chunk core] {len(core_chunk_ids)}, [Chunk relevant] {len(relevant_chunk_ids)} (top_k={top_k})")
            return core_chunk_ids, relevant_chunk_ids

        except Exception as e:
            logger.error(f"[Chunk Relevence] Error: {e}")
            return [], []


    # ──────────────────────────────────────────────────────────
    # Guide Classification
    # ──────────────────────────────────────────────────────────
    async def guide_cls(self, base_query: str) -> str:
        class GuideClsResponse(BaseModel):
            reason: str = Field(description="분류 이유에 대해서 간략히 설명")
            classification: str = Field(description="분류 결과")

        try:
            result = await self._structured_call(
                system_prompt=GUIDE_CLS_SYSTEM_PROMPT,
                user_prompt=GUIDE_CLS_USER_PROMPT.format(base_query=base_query),
                response_model=GuideClsResponse,
            )

            classification = result.get("classification", "")
            if isinstance(classification, str) and classification:
                return classification

            logger.error("[Guide CLS] Invalid response.")
            return []
        except Exception as e:
            logger.error(f"[Guide CLS] Error: {e}")
            return []
