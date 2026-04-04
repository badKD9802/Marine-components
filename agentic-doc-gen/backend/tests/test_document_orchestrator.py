"""
Document Orchestrator 테스트

전체 문서 생성 파이프라인을 검증한다.
plan_document, write_section, review_document, build_hwpx/pptx/xlsx를 모두 mock하여:
- template_id 없을 때 need_template_selection 반환
- 전체 파이프라인 성공 (plan -> write -> build -> review pass)
- review 미달 시 재작성 (최대 2회)
- review 통과 시 파일 경로 반환
- Writer 실패 시 에러 반환
- output_formats에 따른 Builder 호출 (hwpx만, pptx만, 둘 다)
- DB 저장 건너뛰기 (session_id=None)
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

# 프로젝트 모듈
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── 헬퍼 ───


def _run(coro):
    """async 함수를 동기적으로 실행하는 헬퍼."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _sample_plan_dict(
    title="선박 점검 보고서",
    doc_type="보고서",
    template_id="tpl-001",
    output_formats=None,
    num_sections=2,
):
    """DocumentPlan.model_dump() 형태의 딕셔너리를 반환한다."""
    if output_formats is None:
        output_formats = ["hwpx"]
    sections = []
    for i in range(num_sections):
        sections.append({
            "section_index": i,
            "section_title": f"섹션 {i + 1}",
            "instruction": f"섹션 {i + 1}을 작성하세요.",
            "template_content": f"양식 구조 {i + 1}",
            "examples": [f"예시 {i + 1}"],
            "reference_content": "참고 내용",
        })
    return {
        "title": title,
        "doc_type": doc_type,
        "template_id": template_id,
        "output_formats": output_formats,
        "sections": sections,
        "reference_summary": "참고 요약",
    }


def _sample_section_output(section_index=0, section_title="섹션 1"):
    """write_section 반환 형태의 SectionOutput dict."""
    return {
        "section_id": f"sec_{section_index:02d}",
        "section_title": section_title,
        "elements": [
            {"type": "paragraph", "content": {"text": f"{section_title} 본문 내용입니다."}},
        ],
    }


def _sample_review_passed(total_score=0.95):
    """review_document 통과 반환값."""
    return {
        "status": "success",
        "passed": True,
        "total_score": total_score,
        "scores": [
            {"criterion": "completeness", "score": 1.0, "feedback": ""},
            {"criterion": "accuracy", "score": 1.0, "feedback": ""},
            {"criterion": "format_compliance", "score": 1.0, "feedback": ""},
            {"criterion": "clarity", "score": 1.0, "feedback": ""},
            {"criterion": "coherence", "score": 0.0, "feedback": "일부 일관성 부족"},
        ],
        "feedback": ["일부 일관성 부족"],
        "message": f"통과 ({int(total_score * 100)}점)",
    }


def _sample_review_failed(total_score=0.50):
    """review_document 미달 반환값."""
    return {
        "status": "success",
        "passed": False,
        "total_score": total_score,
        "scores": [
            {"criterion": "completeness", "score": 0.0, "feedback": "필수 항목 누락"},
            {"criterion": "accuracy", "score": 1.0, "feedback": ""},
            {"criterion": "format_compliance", "score": 0.0, "feedback": "형식 미준수"},
            {"criterion": "clarity", "score": 1.0, "feedback": ""},
            {"criterion": "coherence", "score": 0.0, "feedback": "일관성 부족"},
        ],
        "feedback": ["필수 항목 누락", "형식 미준수", "일관성 부족"],
        "message": f"재작성 필요 ({int(total_score * 100)}점, 기준 미달: 완성도, 형식 준수, 일관성)",
    }


# ─── 1. template_id 없을 때 need_template_selection 반환 ───


class TestGenerateDocumentNeedTemplateSelection:
    """template_id가 없을 때 plan_document가 need_template_selection을 반환하면
    orchestrator도 그대로 반환해야 한다."""

    @patch("react_system.tools.document_orchestrator.plan_document", new_callable=AsyncMock)
    def test_should_return_need_template_selection_when_no_template_id(self, mock_plan):
        from react_system.tools.document_orchestrator import generate_document

        mock_plan.return_value = {
            "status": "need_template_selection",
            "candidates": [
                {"id": "tpl-001", "title": "양식 1", "category": "안전", "score": 0.9},
                {"id": "tpl-002", "title": "양식 2", "category": "정비", "score": 0.8},
            ],
            "message": "어떤 양식으로 작성할까요?",
        }

        result = _run(generate_document(
            user_request="선박 점검 보고서를 작성해주세요",
        ))

        assert result["status"] == "need_template_selection"
        assert "candidates" in result
        assert len(result["candidates"]) == 2
        assert "message" in result


# ─── 2. 전체 파이프라인 성공 (plan -> write -> build -> review pass) ───


class TestGenerateDocumentFullPipelineSuccess:
    """전체 파이프라인이 성공적으로 동작하는 경우."""

    @patch("react_system.tools.document_orchestrator.review_document", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.build_hwpx", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.write_section", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.plan_document", new_callable=AsyncMock)
    def test_should_return_success_with_files_and_review(
        self, mock_plan, mock_write, mock_build_hwpx, mock_review
    ):
        from react_system.tools.document_orchestrator import generate_document

        plan_dict = _sample_plan_dict(num_sections=2, output_formats=["hwpx"])
        mock_plan.return_value = {
            "status": "success",
            "plan": plan_dict,
            "message": "문서 생성 계획이 수립되었습니다.",
        }
        mock_write.side_effect = [
            {"status": "success", "section": _sample_section_output(0, "섹션 1"), "message": "OK"},
            {"status": "success", "section": _sample_section_output(1, "섹션 2"), "message": "OK"},
        ]
        mock_build_hwpx.return_value = {
            "status": "success",
            "file_path": "/tmp/test.hwpx",
            "message": "HWPX 생성 완료",
        }
        mock_review.return_value = _sample_review_passed(0.95)

        result = _run(generate_document(
            user_request="선박 점검 보고서를 작성해주세요",
            template_id="tpl-001",
        ))

        assert result["status"] == "success"
        assert "doc_id" in result
        assert result["files"]["hwpx"] == "/tmp/test.hwpx"
        assert result["review"]["passed"] is True
        assert result["review"]["total_score"] == 0.95
        assert len(result["sections"]) == 2
        assert "message" in result

    @patch("react_system.tools.document_orchestrator.review_document", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.build_hwpx", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.write_section", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.plan_document", new_callable=AsyncMock)
    def test_should_call_write_section_for_each_section_plan(
        self, mock_plan, mock_write, mock_build_hwpx, mock_review
    ):
        from react_system.tools.document_orchestrator import generate_document

        plan_dict = _sample_plan_dict(num_sections=3, output_formats=["hwpx"])
        mock_plan.return_value = {
            "status": "success",
            "plan": plan_dict,
            "message": "OK",
        }
        mock_write.side_effect = [
            {"status": "success", "section": _sample_section_output(i, f"섹션 {i + 1}"), "message": "OK"}
            for i in range(3)
        ]
        mock_build_hwpx.return_value = {
            "status": "success",
            "file_path": "/tmp/test.hwpx",
            "message": "OK",
        }
        mock_review.return_value = _sample_review_passed()

        _run(generate_document(
            user_request="보고서 작성",
            template_id="tpl-001",
        ))

        assert mock_write.call_count == 3


# ─── 3. review 미달 시 재작성 (최대 2회) ───


class TestGenerateDocumentReviewRetry:
    """review 미달 시 재작성 로직 검증."""

    @patch("react_system.tools.document_orchestrator.review_document", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.build_hwpx", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.write_section", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.plan_document", new_callable=AsyncMock)
    def test_should_retry_write_when_review_fails(
        self, mock_plan, mock_write, mock_build_hwpx, mock_review
    ):
        """리뷰 미달 시 섹션을 재작성하고 다시 리뷰해야 한다."""
        from react_system.tools.document_orchestrator import generate_document

        plan_dict = _sample_plan_dict(num_sections=1, output_formats=["hwpx"])
        mock_plan.return_value = {
            "status": "success",
            "plan": plan_dict,
            "message": "OK",
        }
        # 최초 작성 (1회) + 재작성 (1회) = 총 2회
        mock_write.side_effect = [
            {"status": "success", "section": _sample_section_output(0, "섹션 1"), "message": "OK"},
            {"status": "success", "section": _sample_section_output(0, "섹션 1 개선"), "message": "OK"},
        ]
        mock_build_hwpx.return_value = {
            "status": "success",
            "file_path": "/tmp/test.hwpx",
            "message": "OK",
        }
        # 첫 리뷰 실패, 두 번째 리뷰 통과
        mock_review.side_effect = [
            _sample_review_failed(0.50),
            _sample_review_passed(0.90),
        ]

        result = _run(generate_document(
            user_request="보고서 작성",
            template_id="tpl-001",
        ))

        assert result["status"] == "success"
        assert result["review"]["passed"] is True
        # write_section: 최초 1회 + 재작성 1회 = 2회
        assert mock_write.call_count == 2
        # review_document: 2회 호출
        assert mock_review.call_count == 2

    @patch("react_system.tools.document_orchestrator.review_document", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.build_hwpx", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.write_section", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.plan_document", new_callable=AsyncMock)
    def test_should_stop_retry_after_max_retries(
        self, mock_plan, mock_write, mock_build_hwpx, mock_review
    ):
        """최대 재작성 횟수(2회)를 초과하면 마지막 결과를 반환해야 한다."""
        from react_system.tools.document_orchestrator import generate_document, MAX_REVIEW_RETRIES

        plan_dict = _sample_plan_dict(num_sections=1, output_formats=["hwpx"])
        mock_plan.return_value = {
            "status": "success",
            "plan": plan_dict,
            "message": "OK",
        }
        # 최초 작성 (1회) + 재작성 (2회) = 총 3회
        mock_write.side_effect = [
            {"status": "success", "section": _sample_section_output(0, "섹션 1"), "message": "OK"},
            {"status": "success", "section": _sample_section_output(0, "섹션 1 v2"), "message": "OK"},
            {"status": "success", "section": _sample_section_output(0, "섹션 1 v3"), "message": "OK"},
        ]
        mock_build_hwpx.return_value = {
            "status": "success",
            "file_path": "/tmp/test.hwpx",
            "message": "OK",
        }
        # 모든 리뷰 실패 (3회 리뷰)
        mock_review.side_effect = [
            _sample_review_failed(0.50),
            _sample_review_failed(0.55),
            _sample_review_failed(0.60),
        ]

        result = _run(generate_document(
            user_request="보고서 작성",
            template_id="tpl-001",
        ))

        # 최대 재작성 후에도 미달이면 그 상태로 반환
        assert result["status"] == "success"
        assert result["review"]["passed"] is False
        # review: 최초 + MAX_REVIEW_RETRIES 회 = 3회
        assert mock_review.call_count == MAX_REVIEW_RETRIES + 1

    @patch("react_system.tools.document_orchestrator.review_document", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.build_hwpx", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.write_section", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.plan_document", new_callable=AsyncMock)
    def test_should_pass_feedback_to_rewrite_instruction(
        self, mock_plan, mock_write, mock_build_hwpx, mock_review
    ):
        """재작성 시 이전 리뷰 피드백이 instruction에 포함되어야 한다."""
        from react_system.tools.document_orchestrator import generate_document

        plan_dict = _sample_plan_dict(num_sections=1, output_formats=["hwpx"])
        mock_plan.return_value = {
            "status": "success",
            "plan": plan_dict,
            "message": "OK",
        }
        mock_write.side_effect = [
            {"status": "success", "section": _sample_section_output(0, "섹션 1"), "message": "OK"},
            {"status": "success", "section": _sample_section_output(0, "섹션 1 개선"), "message": "OK"},
        ]
        mock_build_hwpx.return_value = {
            "status": "success",
            "file_path": "/tmp/test.hwpx",
            "message": "OK",
        }
        mock_review.side_effect = [
            _sample_review_failed(0.50),
            _sample_review_passed(0.90),
        ]

        _run(generate_document(
            user_request="보고서 작성",
            template_id="tpl-001",
        ))

        # 두 번째 write_section 호출 시 instruction에 피드백이 포함되어야 함
        second_call_kwargs = mock_write.call_args_list[1]
        instruction = second_call_kwargs.kwargs.get("instruction", "")
        assert "이전 피드백" in instruction
        # 실제 피드백 내용도 포함되어야 함
        assert "필수 항목 누락" in instruction


# ─── 4. Writer 실패 시 에러 반환 ───


class TestGenerateDocumentWriterError:
    """write_section 실패 시 에러 반환."""

    @patch("react_system.tools.document_orchestrator.write_section", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.plan_document", new_callable=AsyncMock)
    def test_should_return_error_when_all_sections_fail(self, mock_plan, mock_write):
        from react_system.tools.document_orchestrator import generate_document

        plan_dict = _sample_plan_dict(num_sections=2, output_formats=["hwpx"])
        mock_plan.return_value = {
            "status": "success",
            "plan": plan_dict,
            "message": "OK",
        }
        mock_write.return_value = {
            "status": "error",
            "message": "LLM 호출 실패",
        }

        result = _run(generate_document(
            user_request="보고서 작성",
            template_id="tpl-001",
        ))

        assert result["status"] == "error"
        assert "섹션 생성 실패" in result["message"]


# ─── 5. output_formats에 따른 Builder 호출 ───


class TestGenerateDocumentOutputFormats:
    """output_formats에 따라 올바른 Builder가 호출되는지 검증."""

    @patch("react_system.tools.document_orchestrator.review_document", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.build_hwpx", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.write_section", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.plan_document", new_callable=AsyncMock)
    def test_should_call_only_hwpx_builder_when_hwpx_format(
        self, mock_plan, mock_write, mock_build_hwpx, mock_review
    ):
        from react_system.tools.document_orchestrator import generate_document

        plan_dict = _sample_plan_dict(num_sections=1, output_formats=["hwpx"])
        mock_plan.return_value = {"status": "success", "plan": plan_dict, "message": "OK"}
        mock_write.return_value = {
            "status": "success",
            "section": _sample_section_output(0, "섹션 1"),
            "message": "OK",
        }
        mock_build_hwpx.return_value = {
            "status": "success",
            "file_path": "/tmp/test.hwpx",
            "message": "OK",
        }
        mock_review.return_value = _sample_review_passed()

        result = _run(generate_document(
            user_request="보고서",
            template_id="tpl-001",
        ))

        mock_build_hwpx.assert_called_once()
        assert "hwpx" in result["files"]

    @patch("react_system.tools.document_orchestrator.review_document", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.build_pptx", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.write_section", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.plan_document", new_callable=AsyncMock)
    def test_should_call_only_pptx_builder_when_pptx_format(
        self, mock_plan, mock_write, mock_build_pptx, mock_review
    ):
        from react_system.tools.document_orchestrator import generate_document

        plan_dict = _sample_plan_dict(num_sections=1, output_formats=["pptx"])
        mock_plan.return_value = {"status": "success", "plan": plan_dict, "message": "OK"}
        mock_write.return_value = {
            "status": "success",
            "section": _sample_section_output(0, "섹션 1"),
            "message": "OK",
        }
        mock_build_pptx.return_value = {
            "status": "success",
            "file_path": "/tmp/test.pptx",
            "message": "OK",
        }
        mock_review.return_value = _sample_review_passed()

        result = _run(generate_document(
            user_request="보고서",
            template_id="tpl-001",
        ))

        mock_build_pptx.assert_called_once()
        assert "pptx" in result["files"]

    @patch("react_system.tools.document_orchestrator.review_document", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.build_xlsx", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.build_pptx", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.build_hwpx", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.write_section", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.plan_document", new_callable=AsyncMock)
    def test_should_call_multiple_builders_when_multiple_formats(
        self, mock_plan, mock_write, mock_build_hwpx, mock_build_pptx, mock_build_xlsx, mock_review
    ):
        from react_system.tools.document_orchestrator import generate_document

        plan_dict = _sample_plan_dict(num_sections=1, output_formats=["hwpx", "pptx", "xlsx"])
        mock_plan.return_value = {"status": "success", "plan": plan_dict, "message": "OK"}
        mock_write.return_value = {
            "status": "success",
            "section": _sample_section_output(0, "섹션 1"),
            "message": "OK",
        }
        mock_build_hwpx.return_value = {"status": "success", "file_path": "/tmp/t.hwpx", "message": "OK"}
        mock_build_pptx.return_value = {"status": "success", "file_path": "/tmp/t.pptx", "message": "OK"}
        mock_build_xlsx.return_value = {"status": "success", "file_path": "/tmp/t.xlsx", "message": "OK"}
        mock_review.return_value = _sample_review_passed()

        result = _run(generate_document(
            user_request="보고서",
            template_id="tpl-001",
        ))

        mock_build_hwpx.assert_called_once()
        mock_build_pptx.assert_called_once()
        mock_build_xlsx.assert_called_once()
        assert result["files"]["hwpx"] == "/tmp/t.hwpx"
        assert result["files"]["pptx"] == "/tmp/t.pptx"
        assert result["files"]["xlsx"] == "/tmp/t.xlsx"


# ─── 6. DB 저장 건너뛰기 (session_id=None) ───


class TestGenerateDocumentDbSkip:
    """session_id가 None이면 DB 저장을 건너뛰어야 한다."""

    @patch("react_system.tools.document_orchestrator.document_db")
    @patch("react_system.tools.document_orchestrator.review_document", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.build_hwpx", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.write_section", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.plan_document", new_callable=AsyncMock)
    def test_should_not_call_db_when_session_id_is_none(
        self, mock_plan, mock_write, mock_build_hwpx, mock_review, mock_db
    ):
        from react_system.tools.document_orchestrator import generate_document

        plan_dict = _sample_plan_dict(num_sections=1, output_formats=["hwpx"])
        mock_plan.return_value = {"status": "success", "plan": plan_dict, "message": "OK"}
        mock_write.return_value = {
            "status": "success",
            "section": _sample_section_output(0, "섹션 1"),
            "message": "OK",
        }
        mock_build_hwpx.return_value = {"status": "success", "file_path": "/tmp/t.hwpx", "message": "OK"}
        mock_review.return_value = _sample_review_passed()
        mock_db.create_document = AsyncMock()
        mock_db.update_document_status = AsyncMock()

        result = _run(generate_document(
            user_request="보고서",
            template_id="tpl-001",
            session_id=None,
        ))

        assert result["status"] == "success"
        mock_db.create_document.assert_not_called()
        mock_db.update_document_status.assert_not_called()

    @patch("react_system.tools.document_orchestrator.document_db")
    @patch("react_system.tools.document_orchestrator.review_document", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.build_hwpx", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.write_section", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.plan_document", new_callable=AsyncMock)
    def test_should_call_db_when_session_id_provided(
        self, mock_plan, mock_write, mock_build_hwpx, mock_review, mock_db
    ):
        from react_system.tools.document_orchestrator import generate_document

        plan_dict = _sample_plan_dict(num_sections=1, output_formats=["hwpx"])
        mock_plan.return_value = {"status": "success", "plan": plan_dict, "message": "OK"}
        mock_write.return_value = {
            "status": "success",
            "section": _sample_section_output(0, "섹션 1"),
            "message": "OK",
        }
        mock_build_hwpx.return_value = {"status": "success", "file_path": "/tmp/t.hwpx", "message": "OK"}
        mock_review.return_value = _sample_review_passed()
        mock_db.create_document = AsyncMock(return_value="doc_test123")
        mock_db.update_document_status = AsyncMock()

        result = _run(generate_document(
            user_request="보고서",
            template_id="tpl-001",
            session_id="sess-001",
            user_id="user-001",
        ))

        assert result["status"] == "success"
        mock_db.create_document.assert_called_once()
        mock_db.update_document_status.assert_called_once_with("doc_test123", "completed")


# ─── 7. plan_document 에러 전파 ───


class TestGenerateDocumentPlanError:
    """plan_document가 에러를 반환하면 orchestrator도 에러를 반환해야 한다."""

    @patch("react_system.tools.document_orchestrator.plan_document", new_callable=AsyncMock)
    def test_should_return_error_when_plan_fails(self, mock_plan):
        from react_system.tools.document_orchestrator import generate_document

        mock_plan.return_value = {
            "status": "error",
            "message": "양식 조회 실패",
        }

        result = _run(generate_document(
            user_request="보고서",
            template_id="tpl-999",
        ))

        assert result["status"] == "error"
        assert "양식 조회 실패" in result["message"]


# ─── 8. write_section에 doc_id 전달 ───


class TestGenerateDocumentDocIdPassing:
    """write_section 호출 시 doc_id를 올바르게 전달하는지 검증."""

    @patch("react_system.tools.document_orchestrator.document_db")
    @patch("react_system.tools.document_orchestrator.review_document", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.build_hwpx", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.write_section", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.plan_document", new_callable=AsyncMock)
    def test_should_pass_doc_id_to_write_section_when_session_id_provided(
        self, mock_plan, mock_write, mock_build_hwpx, mock_review, mock_db
    ):
        from react_system.tools.document_orchestrator import generate_document

        plan_dict = _sample_plan_dict(num_sections=1, output_formats=["hwpx"])
        mock_plan.return_value = {"status": "success", "plan": plan_dict, "message": "OK"}
        mock_write.return_value = {
            "status": "success",
            "section": _sample_section_output(0, "섹션 1"),
            "message": "OK",
        }
        mock_build_hwpx.return_value = {"status": "success", "file_path": "/tmp/t.hwpx", "message": "OK"}
        mock_review.return_value = _sample_review_passed()
        mock_db.create_document = AsyncMock(return_value="doc_abc123")
        mock_db.update_document_status = AsyncMock()

        _run(generate_document(
            user_request="보고서",
            template_id="tpl-001",
            session_id="sess-001",
        ))

        # write_section 호출 시 doc_id가 전달되어야 함
        call_kwargs = mock_write.call_args_list[0].kwargs
        assert call_kwargs.get("doc_id") == "doc_abc123"

    @patch("react_system.tools.document_orchestrator.review_document", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.build_hwpx", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.write_section", new_callable=AsyncMock)
    @patch("react_system.tools.document_orchestrator.plan_document", new_callable=AsyncMock)
    def test_should_pass_none_doc_id_when_no_session_id(
        self, mock_plan, mock_write, mock_build_hwpx, mock_review
    ):
        from react_system.tools.document_orchestrator import generate_document

        plan_dict = _sample_plan_dict(num_sections=1, output_formats=["hwpx"])
        mock_plan.return_value = {"status": "success", "plan": plan_dict, "message": "OK"}
        mock_write.return_value = {
            "status": "success",
            "section": _sample_section_output(0, "섹션 1"),
            "message": "OK",
        }
        mock_build_hwpx.return_value = {"status": "success", "file_path": "/tmp/t.hwpx", "message": "OK"}
        mock_review.return_value = _sample_review_passed()

        _run(generate_document(
            user_request="보고서",
            template_id="tpl-001",
            session_id=None,
        ))

        # session_id가 None이면 doc_id도 None이어야 함
        call_kwargs = mock_write.call_args_list[0].kwargs
        assert call_kwargs.get("doc_id") is None
