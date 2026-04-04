"""
Document Reviewer 테스트

문서 품질 체크리스트 기반 평가 도구의 동작을 검증한다.
LLM 호출은 mock으로 대체하여 단위 테스트를 수행한다.
"""

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 프로젝트 모듈
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from react_system.tools.document_reviewer import (
    PASS_THRESHOLD,
    REVIEW_CRITERIA,
    _evaluate_criterion,
    review_document,
)


# ─── 헬퍼 ───


def _run(coro):
    """async 함수를 동기적으로 실행하는 헬퍼."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_llm_response(verdict: str, reasoning: str = "평가 근거", feedback: str = ""):
    """LLM 응답 mock 객체를 생성한다."""
    content = json.dumps(
        {"reasoning": reasoning, "verdict": verdict, "feedback": feedback},
        ensure_ascii=False,
    )
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


def _make_client_mock(responses: list):
    """AsyncOpenAI 클라이언트 mock을 생성한다. responses는 순서대로 반환된다."""
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=responses)
    return client


# ─── 상수 검증 ───


class TestReviewCriteriaConstants:
    """평가 기준 상수 구조를 검증한다."""

    def test_should_have_five_criteria(self):
        assert len(REVIEW_CRITERIA) == 5

    def test_should_have_weights_summing_to_one(self):
        total = sum(c["weight"] for c in REVIEW_CRITERIA.values())
        assert abs(total - 1.0) < 1e-9

    def test_should_have_required_keys_in_each_criterion(self):
        required_keys = {"weight", "name", "prompt", "definition"}
        for key, config in REVIEW_CRITERIA.items():
            assert required_keys.issubset(config.keys()), f"{key}에 필수 키가 누락됨"

    def test_pass_threshold_should_be_080(self):
        assert PASS_THRESHOLD == 0.80


# ─── 개별 기준 평가 ───


class TestEvaluateCriterion:
    """_evaluate_criterion 함수의 동작을 검증한다."""

    def test_should_return_score_1_for_yes_verdict(self):
        response = _make_llm_response("Yes", feedback="충분합니다")
        client = _make_client_mock([response])

        with patch(
            "react_system.tools.document_reviewer.AsyncOpenAI", return_value=client
        ):
            result = _run(
                _evaluate_criterion(
                    "completeness",
                    REVIEW_CRITERIA["completeness"],
                    '{"title": "테스트"}',
                    "보고서 작성",
                    "",
                )
            )

        assert result["criterion"] == "completeness"
        assert result["score"] == 1.0
        assert result["feedback"] == "충분합니다"

    def test_should_return_score_0_for_no_verdict(self):
        response = _make_llm_response("No", feedback="내용이 부족합니다")
        client = _make_client_mock([response])

        with patch(
            "react_system.tools.document_reviewer.AsyncOpenAI", return_value=client
        ):
            result = _run(
                _evaluate_criterion(
                    "accuracy",
                    REVIEW_CRITERIA["accuracy"],
                    '{"title": "테스트"}',
                    "보고서 작성",
                    "",
                )
            )

        assert result["criterion"] == "accuracy"
        assert result["score"] == 0.0
        assert result["feedback"] == "내용이 부족합니다"

    def test_should_include_template_structure_in_prompt(self):
        """프롬프트에 양식 구조가 포함되는지 검증한다."""
        response = _make_llm_response("Yes")
        client = _make_client_mock([response])

        with patch(
            "react_system.tools.document_reviewer.AsyncOpenAI", return_value=client
        ):
            _run(
                _evaluate_criterion(
                    "format_compliance",
                    REVIEW_CRITERIA["format_compliance"],
                    '{"title": "테스트"}',
                    "보고서 작성",
                    "1. 제목 2. 본문 3. 결론",
                )
            )

        # LLM 호출 시 전달된 메시지를 검증
        call_args = client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        user_message = messages[-1]["content"]
        assert "1. 제목 2. 본문 3. 결론" in user_message

    def test_should_return_score_0_on_llm_failure(self):
        """LLM 호출 실패 시 해당 기준 score=0으로 처리한다."""
        client = AsyncMock()
        client.chat.completions.create = AsyncMock(
            side_effect=Exception("API 오류")
        )

        with patch(
            "react_system.tools.document_reviewer.AsyncOpenAI", return_value=client
        ):
            result = _run(
                _evaluate_criterion(
                    "clarity",
                    REVIEW_CRITERIA["clarity"],
                    '{"title": "테스트"}',
                    "보고서 작성",
                    "",
                )
            )

        assert result["criterion"] == "clarity"
        assert result["score"] == 0.0
        assert "오류" in result["feedback"] or "실패" in result["feedback"]

    def test_should_use_json_response_format(self):
        """LLM 호출 시 JSON response_format을 사용하는지 검증한다."""
        response = _make_llm_response("Yes")
        client = _make_client_mock([response])

        with patch(
            "react_system.tools.document_reviewer.AsyncOpenAI", return_value=client
        ):
            _run(
                _evaluate_criterion(
                    "coherence",
                    REVIEW_CRITERIA["coherence"],
                    '{"title": "테스트"}',
                    "보고서 작성",
                    "",
                )
            )

        call_args = client.chat.completions.create.call_args
        response_format = call_args.kwargs.get("response_format")
        assert response_format == {"type": "json_object"}

    def test_should_use_low_temperature(self):
        """일관성을 위해 temperature=0.1을 사용하는지 검증한다."""
        response = _make_llm_response("Yes")
        client = _make_client_mock([response])

        with patch(
            "react_system.tools.document_reviewer.AsyncOpenAI", return_value=client
        ):
            _run(
                _evaluate_criterion(
                    "completeness",
                    REVIEW_CRITERIA["completeness"],
                    '{"title": "테스트"}',
                    "보고서 작성",
                    "",
                )
            )

        call_args = client.chat.completions.create.call_args
        temperature = call_args.kwargs.get("temperature")
        assert temperature == 0.1


# ─── 문서 평가 통합 ───


class TestReviewDocumentAllPass:
    """모든 기준을 통과하는 경우를 검증한다."""

    def test_should_pass_when_all_criteria_yes(self):
        responses = [_make_llm_response("Yes", feedback=f"기준 {i} 통과") for i in range(5)]
        client = _make_client_mock(responses)

        with patch(
            "react_system.tools.document_reviewer.AsyncOpenAI", return_value=client
        ):
            result = _run(
                review_document(
                    document_json='{"title": "테스트 문서"}',
                    original_request="월간 보고서 작성",
                )
            )

        assert result["status"] == "success"
        assert result["passed"] is True
        assert result["total_score"] == 1.0
        assert len(result["scores"]) == 5
        assert result["feedback"] == []
        assert "통과" in result["message"]


class TestReviewDocumentPartialPass:
    """일부 기준만 통과하는 경우를 검증한다."""

    def test_should_calculate_weighted_score_correctly(self):
        """completeness(0.25)+accuracy(0.25)+format(0.20) = Yes, clarity(0.15)+coherence(0.15) = No
        → 가중 합산 = 0.25 + 0.25 + 0.20 = 0.70
        """
        # 기준 순서: completeness, accuracy, format_compliance, clarity, coherence
        responses = [
            _make_llm_response("Yes"),   # completeness 0.25
            _make_llm_response("Yes"),   # accuracy 0.25
            _make_llm_response("Yes"),   # format_compliance 0.20
            _make_llm_response("No", feedback="명확성 부족"),    # clarity 0.15
            _make_llm_response("No", feedback="일관성 부족"),    # coherence 0.15
        ]
        client = _make_client_mock(responses)

        with patch(
            "react_system.tools.document_reviewer.AsyncOpenAI", return_value=client
        ):
            result = _run(
                review_document(
                    document_json='{"title": "테스트"}',
                    original_request="보고서 작성",
                )
            )

        assert result["status"] == "success"
        assert result["passed"] is False
        assert abs(result["total_score"] - 0.70) < 1e-9
        assert len(result["feedback"]) == 2
        assert "명확성 부족" in result["feedback"]
        assert "일관성 부족" in result["feedback"]

    def test_should_include_failed_criteria_in_message(self):
        """미달 기준 이름이 message에 포함되는지 검증한다."""
        responses = [
            _make_llm_response("Yes"),   # completeness
            _make_llm_response("No", feedback="수치 오류"),   # accuracy
            _make_llm_response("Yes"),   # format_compliance
            _make_llm_response("Yes"),   # clarity
            _make_llm_response("No", feedback="문체 불일치"),  # coherence
        ]
        client = _make_client_mock(responses)

        with patch(
            "react_system.tools.document_reviewer.AsyncOpenAI", return_value=client
        ):
            result = _run(
                review_document(
                    document_json='{"title": "테스트"}',
                    original_request="보고서 작성",
                )
            )

        assert "재작성 필요" in result["message"]
        assert "정확성" in result["message"]
        assert "일관성" in result["message"]


class TestReviewDocumentAllFail:
    """모든 기준이 미달인 경우를 검증한다."""

    def test_should_fail_with_zero_score(self):
        responses = [
            _make_llm_response("No", feedback=f"기준 {i} 미달") for i in range(5)
        ]
        client = _make_client_mock(responses)

        with patch(
            "react_system.tools.document_reviewer.AsyncOpenAI", return_value=client
        ):
            result = _run(
                review_document(
                    document_json='{"title": "테스트"}',
                    original_request="보고서 작성",
                )
            )

        assert result["status"] == "success"
        assert result["passed"] is False
        assert result["total_score"] == 0.0
        assert len(result["feedback"]) == 5


class TestReviewDocumentThresholdBoundary:
    """PASS_THRESHOLD 경계값을 검증한다."""

    def test_should_pass_at_exactly_080(self):
        """정확히 0.80일 때 통과해야 한다.
        completeness(0.25) + accuracy(0.25) + format(0.20) + clarity(0.15) = 0.85
        → 이건 0.85이므로 0.80보다 높다.

        정확히 0.80을 만들려면:
        completeness(0.25) + accuracy(0.25) + format(0.20) + coherence(0.15) = 0.85 (X)

        실제로 0.80 정확히 맞추는 조합:
        completeness(0.25) + accuracy(0.25) + clarity(0.15) + coherence(0.15) = 0.80
        → format_compliance만 No
        """
        responses = [
            _make_llm_response("Yes"),   # completeness 0.25
            _make_llm_response("Yes"),   # accuracy 0.25
            _make_llm_response("No", feedback="형식 미준수"),   # format_compliance 0.20
            _make_llm_response("Yes"),   # clarity 0.15
            _make_llm_response("Yes"),   # coherence 0.15
        ]
        client = _make_client_mock(responses)

        with patch(
            "react_system.tools.document_reviewer.AsyncOpenAI", return_value=client
        ):
            result = _run(
                review_document(
                    document_json='{"title": "테스트"}',
                    original_request="보고서 작성",
                )
            )

        assert result["passed"] is True
        assert abs(result["total_score"] - 0.80) < 1e-9

    def test_should_fail_just_below_080(self):
        """0.80 미만이면 미달이어야 한다.
        completeness(0.25) + accuracy(0.25) + format(0.20) = 0.70
        """
        responses = [
            _make_llm_response("Yes"),   # completeness 0.25
            _make_llm_response("Yes"),   # accuracy 0.25
            _make_llm_response("Yes"),   # format_compliance 0.20
            _make_llm_response("No", feedback="명확성 부족"),   # clarity 0.15
            _make_llm_response("No", feedback="일관성 부족"),   # coherence 0.15
        ]
        client = _make_client_mock(responses)

        with patch(
            "react_system.tools.document_reviewer.AsyncOpenAI", return_value=client
        ):
            result = _run(
                review_document(
                    document_json='{"title": "테스트"}',
                    original_request="보고서 작성",
                )
            )

        assert result["passed"] is False
        assert abs(result["total_score"] - 0.70) < 1e-9


class TestReviewDocumentLLMFailure:
    """LLM 호출 실패 시 처리를 검증한다."""

    def test_should_treat_failed_criterion_as_zero(self):
        """LLM 실패한 기준은 score=0으로 처리한다."""
        responses = [
            _make_llm_response("Yes"),                          # completeness 0.25
            Exception("API 오류"),                               # accuracy → 0
            _make_llm_response("Yes"),                          # format_compliance 0.20
            _make_llm_response("Yes"),                          # clarity 0.15
            _make_llm_response("Yes"),                          # coherence 0.15
        ]
        client = _make_client_mock(responses)

        with patch(
            "react_system.tools.document_reviewer.AsyncOpenAI", return_value=client
        ):
            result = _run(
                review_document(
                    document_json='{"title": "테스트"}',
                    original_request="보고서 작성",
                )
            )

        assert result["status"] == "success"
        # 0.25 + 0 + 0.20 + 0.15 + 0.15 = 0.75
        assert abs(result["total_score"] - 0.75) < 1e-9
        assert result["passed"] is False


class TestReviewDocumentModelConfig:
    """모델 설정을 검증한다."""

    def test_should_use_env_model_or_default(self):
        """환경변수 REVIEWER_LLM_MODEL 또는 기본값 gpt-4o-mini를 사용한다."""
        responses = [_make_llm_response("Yes") for _ in range(5)]
        client = _make_client_mock(responses)

        with patch(
            "react_system.tools.document_reviewer.AsyncOpenAI", return_value=client
        ), patch.dict(os.environ, {}, clear=False):
            # 환경변수 없으면 기본값
            os.environ.pop("REVIEWER_LLM_MODEL", None)
            _run(
                review_document(
                    document_json='{"title": "테스트"}',
                    original_request="보고서 작성",
                )
            )

        call_args = client.chat.completions.create.call_args
        model = call_args.kwargs.get("model")
        assert model == "gpt-4o-mini"

    def test_should_use_env_model_when_set(self):
        """환경변수가 설정되면 해당 모델을 사용한다."""
        responses = [_make_llm_response("Yes") for _ in range(5)]
        client = _make_client_mock(responses)

        with patch(
            "react_system.tools.document_reviewer.AsyncOpenAI", return_value=client
        ), patch.dict(os.environ, {"REVIEWER_LLM_MODEL": "gpt-4o"}, clear=False):
            _run(
                review_document(
                    document_json='{"title": "테스트"}',
                    original_request="보고서 작성",
                )
            )

        call_args = client.chat.completions.create.call_args
        model = call_args.kwargs.get("model")
        assert model == "gpt-4o"
