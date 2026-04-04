"""
Document Writer 도구 테스트

write_section: LLM 호출 → JSON 응답 파싱(SectionOutput) → DB 저장
LLM 호출은 mock으로 대체하여 프롬프트 구조, 파싱, 에러 처리를 검증한다.
"""

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 프로젝트 모듈
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from react_system.document_schema import (
    DocumentElement,
    SectionOutput,
    TextContent,
)


# ─── 헬퍼 ───


def _run(coro):
    """async 함수를 동기적으로 실행하는 헬퍼."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_section_json(
    section_id="sec_01",
    section_title="테스트 섹션",
    elements=None,
) -> str:
    """LLM 응답용 SectionOutput JSON 문자열을 생성한다."""
    if elements is None:
        elements = [
            {
                "type": "paragraph",
                "content": {"text": "본문 내용입니다."},
            }
        ]
    return json.dumps(
        {
            "section_id": section_id,
            "section_title": section_title,
            "elements": elements,
        },
        ensure_ascii=False,
    )


def _mock_openai_response(content: str):
    """AsyncOpenAI chat.completions.create 응답을 흉내내는 mock을 생성한다."""
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


# ─── 테스트 1: _build_writer_prompt 구조 검증 ───


class TestBuildWriterPrompt:
    """_build_writer_prompt 프롬프트 구조 검증"""

    def test_should_return_system_and_user_messages(self):
        """시스템 메시지와 유저 메시지를 포함하는 리스트를 반환해야 한다."""
        from react_system.tools.document_writer import _build_writer_prompt

        messages = _build_writer_prompt(
            section_title="추진 배경",
            instruction="배경을 작성하세요",
            template_content="## 추진 배경\n- 내용",
            examples=["예시 1 내용"],
            reference_content="참고 문서 내용",
        )

        assert isinstance(messages, list)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_should_include_section_title_in_user_message(self):
        """유저 메시지에 섹션 제목이 포함되어야 한다."""
        from react_system.tools.document_writer import _build_writer_prompt

        messages = _build_writer_prompt(
            section_title="사업 개요",
            instruction="개요를 작성하세요",
            template_content="양식",
            examples=[],
            reference_content="참고 내용",
        )

        assert "사업 개요" in messages[1]["content"]

    def test_should_include_instruction_in_user_message(self):
        """유저 메시지에 지시사항이 포함되어야 한다."""
        from react_system.tools.document_writer import _build_writer_prompt

        messages = _build_writer_prompt(
            section_title="제목",
            instruction="구체적으로 3문단 이상 작성하세요",
            template_content="양식",
            examples=[],
            reference_content="참고",
        )

        assert "구체적으로 3문단 이상 작성하세요" in messages[1]["content"]

    def test_should_include_template_content_in_user_message(self):
        """유저 메시지에 양식 구조가 포함되어야 한다."""
        from react_system.tools.document_writer import _build_writer_prompt

        messages = _build_writer_prompt(
            section_title="제목",
            instruction="지시사항",
            template_content="## 양식 구조 예시\n- 항목1\n- 항목2",
            examples=[],
            reference_content="참고",
        )

        assert "## 양식 구조 예시" in messages[1]["content"]

    def test_should_include_all_examples_in_user_message(self):
        """예시가 여러 개일 때 모든 예시가 유저 메시지에 포함되어야 한다."""
        from react_system.tools.document_writer import _build_writer_prompt

        examples = [
            "첫 번째 예시 내용입니다.",
            "두 번째 예시 내용입니다.",
            "세 번째 예시 내용입니다.",
        ]
        messages = _build_writer_prompt(
            section_title="제목",
            instruction="지시",
            template_content="양식",
            examples=examples,
            reference_content="참고",
        )

        user_content = messages[1]["content"]
        assert "첫 번째 예시 내용입니다." in user_content
        assert "두 번째 예시 내용입니다." in user_content
        assert "세 번째 예시 내용입니다." in user_content
        # 예시 번호도 포함되어야 한다
        assert "예시 1" in user_content
        assert "예시 2" in user_content
        assert "예시 3" in user_content

    def test_should_include_reference_content_in_user_message(self):
        """유저 메시지에 참고문서 내용이 포함되어야 한다."""
        from react_system.tools.document_writer import _build_writer_prompt

        messages = _build_writer_prompt(
            section_title="제목",
            instruction="지시",
            template_content="양식",
            examples=[],
            reference_content="해양 엔진 부품 관련 참고 자료입니다.",
        )

        assert "해양 엔진 부품 관련 참고 자료입니다." in messages[1]["content"]

    def test_should_include_json_schema_in_system_message(self):
        """시스템 메시지에 JSON 스키마가 포함되어야 한다."""
        from react_system.tools.document_writer import _build_writer_prompt

        messages = _build_writer_prompt(
            section_title="제목",
            instruction="지시",
            template_content="양식",
            examples=[],
            reference_content="참고",
        )

        system_content = messages[0]["content"]
        assert "section_id" in system_content
        assert "section_title" in system_content
        assert "elements" in system_content


# ─── 테스트 2: write_section 성공 시나리오 ───


class TestWriteSectionSuccess:
    """write_section 성공 시 SectionOutput 구조 검증"""

    @patch("react_system.tools.document_writer.AsyncOpenAI")
    def test_should_return_success_with_section_output(self, mock_openai_cls):
        """LLM이 유효한 JSON을 반환하면 success 상태와 SectionOutput을 반환해야 한다."""
        from react_system.tools.document_writer import write_section

        # LLM mock 설정
        section_json = _make_section_json(
            section_id="sec_01",
            section_title="추진 배경",
            elements=[
                {"type": "paragraph", "content": {"text": "해양 엔진 시장이 성장하고 있습니다."}},
            ],
        )
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(section_json)
        )
        mock_openai_cls.return_value = mock_client

        result = _run(write_section(
            section_index=0,
            section_title="추진 배경",
            instruction="배경을 작성하세요",
            template_content="양식",
            examples=["예시"],
            reference_content="참고 내용",
        ))

        assert result["status"] == "success"
        assert result["section"]["section_id"] == "sec_01"
        assert result["section"]["section_title"] == "추진 배경"
        assert len(result["section"]["elements"]) == 1
        assert "추진 배경" in result["message"]

    @patch("react_system.tools.document_writer.AsyncOpenAI")
    def test_should_call_llm_with_json_response_format(self, mock_openai_cls):
        """LLM 호출 시 response_format이 json_object로 설정되어야 한다."""
        from react_system.tools.document_writer import write_section

        section_json = _make_section_json()
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(section_json)
        )
        mock_openai_cls.return_value = mock_client

        _run(write_section(
            section_index=0,
            section_title="테스트",
            instruction="작성",
            template_content="양식",
            examples=[],
            reference_content="참고",
        ))

        # create 호출 인자 확인
        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs.get("response_format") == {"type": "json_object"}

    @patch("react_system.tools.document_writer.AsyncOpenAI")
    def test_should_call_llm_with_temperature_03(self, mock_openai_cls):
        """LLM 호출 시 temperature가 0.3이어야 한다."""
        from react_system.tools.document_writer import write_section

        section_json = _make_section_json()
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(section_json)
        )
        mock_openai_cls.return_value = mock_client

        _run(write_section(
            section_index=0,
            section_title="테스트",
            instruction="작성",
            template_content="양식",
            examples=[],
            reference_content="참고",
        ))

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs.get("temperature") == 0.3


# ─── 테스트 3: JSON 파싱 실패 시 에러 ───


class TestWriteSectionJsonError:
    """JSON 파싱 실패 시 에러 반환 검증"""

    @patch("react_system.tools.document_writer.AsyncOpenAI")
    def test_should_return_error_when_llm_returns_invalid_json(self, mock_openai_cls):
        """LLM이 유효하지 않은 JSON을 반환하면 error를 반환해야 한다."""
        from react_system.tools.document_writer import write_section

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response("이것은 JSON이 아닙니다")
        )
        mock_openai_cls.return_value = mock_client

        result = _run(write_section(
            section_index=0,
            section_title="테스트",
            instruction="작성",
            template_content="양식",
            examples=[],
            reference_content="참고",
        ))

        assert result["status"] == "error"
        assert "JSON 파싱 실패" in result["message"]

    @patch("react_system.tools.document_writer.AsyncOpenAI")
    def test_should_return_error_when_json_missing_required_fields(self, mock_openai_cls):
        """JSON에 필수 필드가 누락되면 error를 반환해야 한다."""
        from react_system.tools.document_writer import write_section

        # section_id 누락
        invalid_json = json.dumps({"section_title": "제목"})
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(invalid_json)
        )
        mock_openai_cls.return_value = mock_client

        result = _run(write_section(
            section_index=0,
            section_title="테스트",
            instruction="작성",
            template_content="양식",
            examples=[],
            reference_content="참고",
        ))

        assert result["status"] == "error"
        assert "JSON 파싱 실패" in result["message"]


# ─── 테스트 4: LLM 호출 실패 시 에러 ───


class TestWriteSectionLlmError:
    """LLM 호출 실패 시 에러 반환 검증"""

    @patch("react_system.tools.document_writer.AsyncOpenAI")
    def test_should_return_error_when_llm_raises_exception(self, mock_openai_cls):
        """LLM 호출 중 예외가 발생하면 error를 반환해야 한다."""
        from react_system.tools.document_writer import write_section

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API rate limit exceeded")
        )
        mock_openai_cls.return_value = mock_client

        result = _run(write_section(
            section_index=0,
            section_title="테스트",
            instruction="작성",
            template_content="양식",
            examples=[],
            reference_content="참고",
        ))

        assert result["status"] == "error"
        assert "LLM 호출 실패" in result["message"]
        assert "API rate limit exceeded" in result["message"]


# ─── 테스트 5: doc_id가 있을 때 save_section 호출 ───


class TestWriteSectionDbSave:
    """doc_id 존재 시 DB 저장 동작 검증"""

    @patch("react_system.tools.document_writer.document_db")
    @patch("react_system.tools.document_writer.AsyncOpenAI")
    def test_should_call_save_section_when_doc_id_provided(
        self, mock_openai_cls, mock_doc_db
    ):
        """doc_id가 있으면 document_db.save_section을 호출해야 한다."""
        from react_system.tools.document_writer import write_section

        section_json = _make_section_json(
            section_id="sec_02",
            section_title="사업 개요",
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(section_json)
        )
        mock_openai_cls.return_value = mock_client
        mock_doc_db.save_section = AsyncMock(return_value=1)

        result = _run(write_section(
            section_index=1,
            section_title="사업 개요",
            instruction="개요 작성",
            template_content="양식",
            examples=[],
            reference_content="참고",
            doc_id="doc_abc123",
        ))

        assert result["status"] == "success"
        mock_doc_db.save_section.assert_called_once_with(
            doc_id="doc_abc123",
            section_index=1,
            section_title="사업 개요",
            content=result["section"],
        )

    @patch("react_system.tools.document_writer.document_db")
    @patch("react_system.tools.document_writer.AsyncOpenAI")
    def test_should_not_call_save_section_when_doc_id_is_none(
        self, mock_openai_cls, mock_doc_db
    ):
        """doc_id가 None이면 save_section을 호출하지 않아야 한다."""
        from react_system.tools.document_writer import write_section

        section_json = _make_section_json()
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(section_json)
        )
        mock_openai_cls.return_value = mock_client

        result = _run(write_section(
            section_index=0,
            section_title="테스트",
            instruction="작성",
            template_content="양식",
            examples=[],
            reference_content="참고",
            doc_id=None,
        ))

        assert result["status"] == "success"
        mock_doc_db.save_section.assert_not_called()
