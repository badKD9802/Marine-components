"""
문서 생성 계획 도구 테스트

template_search 함수들을 mock하여 Milvus 연결 없이
plan_document, SectionPlan, DocumentPlan을 검증한다.
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


def _sample_template(
    id_="tpl-001",
    title="선박 점검 보고서",
    category="안전",
    subcategory="점검",
    score=0.95,
):
    """검색 결과 샘플 양식 레코드."""
    return {
        "id": id_,
        "template_id": id_,
        "chunk_type": "template",
        "parent_id": "",
        "title": title,
        "content": f"{title} 양식입니다.",
        "category": category,
        "subcategory": subcategory,
        "visibility": "public",
        "user_id": "",
        "metadata": {},
        "created_at": 1700000000,
        "updated_at": 1700000000,
        "score": score,
    }


def _sample_section(
    id_="sec-001",
    template_id="tpl-001",
    title="1. 선박 정보",
    content="선박명, 선박 번호, 점검 일자 등을 기입합니다.",
):
    """검색 결과 샘플 섹션 레코드."""
    return {
        "id": id_,
        "template_id": template_id,
        "chunk_type": "section",
        "parent_id": template_id,
        "title": title,
        "content": content,
        "category": "안전",
        "subcategory": "점검",
        "visibility": "public",
        "user_id": "",
        "metadata": {},
        "created_at": 1700000000,
        "updated_at": 1700000000,
    }


def _sample_example(
    id_="ex-001",
    template_id="tpl-001",
    title="점검 보고서 예시 1",
    content="예시 내용입니다.",
    user_id="",
    visibility="public",
    parent_id=None,
    chunk_type="example",
):
    """검색 결과 샘플 예시 레코드."""
    return {
        "id": id_,
        "template_id": template_id,
        "chunk_type": chunk_type,
        "parent_id": parent_id or template_id,
        "title": title,
        "content": content,
        "category": "안전",
        "subcategory": "점검",
        "visibility": visibility,
        "user_id": user_id,
        "metadata": {},
        "created_at": 1700000000,
        "updated_at": 1700000000,
    }


# ─── Pydantic 모델 테스트 ───


class TestSectionPlan:
    """SectionPlan 모델 유효성 테스트."""

    def test_should_create_section_plan_with_required_fields(self):
        from react_system.tools.document_planner import SectionPlan

        plan = SectionPlan(
            section_index=0,
            section_title="1. 선박 정보",
            instruction="이 섹션은 1. 선박 정보입니다.",
            template_content="선박명, 선박 번호를 기입합니다.",
            examples=["예시 1 내용"],
            reference_content="참고 내용",
        )

        assert plan.section_index == 0
        assert plan.section_title == "1. 선박 정보"
        assert plan.instruction.startswith("이 섹션은")
        assert len(plan.examples) == 1
        assert plan.reference_content == "참고 내용"

    def test_should_allow_empty_examples_and_reference(self):
        from react_system.tools.document_planner import SectionPlan

        plan = SectionPlan(
            section_index=1,
            section_title="2. 점검 항목",
            instruction="점검 항목을 작성하세요.",
            template_content="점검 내용",
            examples=[],
            reference_content="",
        )

        assert plan.examples == []
        assert plan.reference_content == ""


class TestDocumentPlan:
    """DocumentPlan 모델 유효성 테스트."""

    def test_should_create_document_plan_with_sections(self):
        from react_system.tools.document_planner import DocumentPlan, SectionPlan

        section = SectionPlan(
            section_index=0,
            section_title="1. 선박 정보",
            instruction="지시사항",
            template_content="양식 내용",
            examples=[],
            reference_content="",
        )
        plan = DocumentPlan(
            title="선박 점검 보고서",
            doc_type="보고서",
            template_id="tpl-001",
            output_formats=["hwpx"],
            sections=[section],
            reference_summary="",
        )

        assert plan.title == "선박 점검 보고서"
        assert plan.doc_type == "보고서"
        assert plan.template_id == "tpl-001"
        assert plan.output_formats == ["hwpx"]
        assert len(plan.sections) == 1

    def test_should_default_output_formats_not_enforced_by_model(self):
        """DocumentPlan 모델은 output_formats를 필수로 받음 (기본값은 plan_document에서 처리)."""
        from react_system.tools.document_planner import DocumentPlan

        plan = DocumentPlan(
            title="테스트",
            doc_type="공문",
            template_id="tpl-002",
            output_formats=["hwpx", "pptx"],
            sections=[],
            reference_summary="요약",
        )

        assert plan.output_formats == ["hwpx", "pptx"]
        assert plan.reference_summary == "요약"


# ─── plan_document: template_id 없을 때 ───


class TestPlanDocumentWithoutTemplateId:
    """template_id가 없을 때 양식 추천 동작 테스트."""

    @patch("react_system.tools.document_planner.search_templates", new_callable=AsyncMock)
    def test_should_return_need_template_selection_when_no_template_id(self, mock_search):
        from react_system.tools.document_planner import plan_document

        candidates = [
            _sample_template(id_=f"tpl-{i}", title=f"양식 {i}", score=0.9 - i * 0.1)
            for i in range(5)
        ]
        mock_search.return_value = {
            "status": "success",
            "templates": candidates,
            "total": 5,
        }

        result = _run(plan_document(
            user_request="선박 점검 보고서를 작성해주세요",
        ))

        assert result["status"] == "need_template_selection"
        assert "candidates" in result
        assert len(result["candidates"]) == 5
        assert "message" in result

    @patch("react_system.tools.document_planner.search_templates", new_callable=AsyncMock)
    def test_should_call_search_templates_with_user_request(self, mock_search):
        from react_system.tools.document_planner import plan_document

        mock_search.return_value = {
            "status": "success",
            "templates": [],
            "total": 0,
        }

        _run(plan_document(
            user_request="정비 일지 작성",
            user_id="user123",
        ))

        mock_search.assert_called_once()
        call_args = mock_search.call_args
        assert call_args.kwargs.get("query") == "정비 일지 작성" or call_args[0][0] == "정비 일지 작성"

    @patch("react_system.tools.document_planner.search_templates", new_callable=AsyncMock)
    def test_should_limit_candidates_to_5(self, mock_search):
        from react_system.tools.document_planner import plan_document

        candidates = [
            _sample_template(id_=f"tpl-{i}", title=f"양식 {i}", score=0.9 - i * 0.05)
            for i in range(10)
        ]
        mock_search.return_value = {
            "status": "success",
            "templates": candidates,
            "total": 10,
        }

        result = _run(plan_document(
            user_request="보고서 작성",
        ))

        assert len(result["candidates"]) == 5

    @patch("react_system.tools.document_planner.search_templates", new_callable=AsyncMock)
    def test_should_include_id_title_category_score_in_candidates(self, mock_search):
        from react_system.tools.document_planner import plan_document

        mock_search.return_value = {
            "status": "success",
            "templates": [_sample_template()],
            "total": 1,
        }

        result = _run(plan_document(user_request="점검 보고서"))

        candidate = result["candidates"][0]
        assert "id" in candidate
        assert "title" in candidate
        assert "category" in candidate
        assert "score" in candidate

    @patch("react_system.tools.document_planner.search_templates", new_callable=AsyncMock)
    def test_should_return_error_when_search_fails(self, mock_search):
        from react_system.tools.document_planner import plan_document

        mock_search.return_value = {
            "status": "error",
            "message": "Milvus 연결 실패",
        }

        result = _run(plan_document(user_request="보고서"))

        assert result["status"] == "error"
        assert "Milvus 연결 실패" in result["message"]


# ─── plan_document: template_id 있을 때 ───


class TestPlanDocumentWithTemplateId:
    """template_id가 있을 때 DocumentPlan 생성 테스트."""

    @patch("react_system.tools.document_planner.get_examples_for_template", new_callable=AsyncMock)
    @patch("react_system.tools.document_planner.get_template_detail", new_callable=AsyncMock)
    def test_should_return_success_with_plan(self, mock_detail, mock_examples):
        from react_system.tools.document_planner import plan_document

        mock_detail.return_value = {
            "status": "success",
            "template": _sample_template(id_="tpl-001", title="점검 보고서"),
            "sections": [
                _sample_section(id_="sec-001", title="1. 선박 정보"),
                _sample_section(id_="sec-002", title="2. 점검 항목"),
            ],
        }
        mock_examples.return_value = {
            "status": "success",
            "examples": [
                _sample_example(id_="ex-001", content="예시 1 내용"),
            ],
            "total": 1,
        }

        result = _run(plan_document(
            user_request="점검 보고서 작성",
            template_id="tpl-001",
        ))

        assert result["status"] == "success"
        assert "plan" in result
        assert result["plan"]["title"] == "점검 보고서"
        assert result["plan"]["template_id"] == "tpl-001"
        assert "message" in result

    @patch("react_system.tools.document_planner.get_examples_for_template", new_callable=AsyncMock)
    @patch("react_system.tools.document_planner.get_template_detail", new_callable=AsyncMock)
    def test_should_create_section_plans_for_each_section(self, mock_detail, mock_examples):
        from react_system.tools.document_planner import plan_document

        mock_detail.return_value = {
            "status": "success",
            "template": _sample_template(id_="tpl-001"),
            "sections": [
                _sample_section(id_="sec-001", title="1. 선박 정보", content="선박명 기입"),
                _sample_section(id_="sec-002", title="2. 점검 항목", content="점검 내용"),
                _sample_section(id_="sec-003", title="3. 결론", content="결론 작성"),
            ],
        }
        mock_examples.return_value = {
            "status": "success",
            "examples": [],
            "total": 0,
        }

        result = _run(plan_document(
            user_request="점검 보고서",
            template_id="tpl-001",
        ))

        sections = result["plan"]["sections"]
        assert len(sections) == 3
        assert sections[0]["section_index"] == 0
        assert sections[0]["section_title"] == "1. 선박 정보"
        assert sections[1]["section_index"] == 1
        assert sections[2]["section_index"] == 2

    @patch("react_system.tools.document_planner.get_examples_for_template", new_callable=AsyncMock)
    @patch("react_system.tools.document_planner.get_template_detail", new_callable=AsyncMock)
    def test_should_include_template_content_in_section_plan(self, mock_detail, mock_examples):
        from react_system.tools.document_planner import plan_document

        section_content = "선박명, 선박 번호, 점검 일자 등을 기입합니다."
        mock_detail.return_value = {
            "status": "success",
            "template": _sample_template(id_="tpl-001"),
            "sections": [
                _sample_section(
                    id_="sec-001",
                    title="1. 선박 정보",
                    content=section_content,
                ),
            ],
        }
        mock_examples.return_value = {
            "status": "success",
            "examples": [],
            "total": 0,
        }

        result = _run(plan_document(
            user_request="보고서",
            template_id="tpl-001",
        ))

        section = result["plan"]["sections"][0]
        assert section["template_content"] == section_content

    @patch("react_system.tools.document_planner.get_examples_for_template", new_callable=AsyncMock)
    @patch("react_system.tools.document_planner.get_template_detail", new_callable=AsyncMock)
    def test_should_include_instruction_with_section_title(self, mock_detail, mock_examples):
        from react_system.tools.document_planner import plan_document

        mock_detail.return_value = {
            "status": "success",
            "template": _sample_template(id_="tpl-001"),
            "sections": [
                _sample_section(id_="sec-001", title="1. 선박 정보"),
            ],
        }
        mock_examples.return_value = {
            "status": "success",
            "examples": [],
            "total": 0,
        }

        result = _run(plan_document(
            user_request="보고서",
            template_id="tpl-001",
        ))

        section = result["plan"]["sections"][0]
        assert "1. 선박 정보" in section["instruction"]

    @patch("react_system.tools.document_planner.get_examples_for_template", new_callable=AsyncMock)
    @patch("react_system.tools.document_planner.get_template_detail", new_callable=AsyncMock)
    def test_should_default_output_formats_to_hwpx(self, mock_detail, mock_examples):
        from react_system.tools.document_planner import plan_document

        mock_detail.return_value = {
            "status": "success",
            "template": _sample_template(id_="tpl-001"),
            "sections": [],
        }
        mock_examples.return_value = {
            "status": "success",
            "examples": [],
            "total": 0,
        }

        result = _run(plan_document(
            user_request="보고서",
            template_id="tpl-001",
        ))

        assert result["plan"]["output_formats"] == ["hwpx"]

    @patch("react_system.tools.document_planner.get_examples_for_template", new_callable=AsyncMock)
    @patch("react_system.tools.document_planner.get_template_detail", new_callable=AsyncMock)
    def test_should_use_provided_output_formats(self, mock_detail, mock_examples):
        from react_system.tools.document_planner import plan_document

        mock_detail.return_value = {
            "status": "success",
            "template": _sample_template(id_="tpl-001"),
            "sections": [],
        }
        mock_examples.return_value = {
            "status": "success",
            "examples": [],
            "total": 0,
        }

        result = _run(plan_document(
            user_request="보고서",
            template_id="tpl-001",
            output_formats=["hwpx", "pptx"],
        ))

        assert result["plan"]["output_formats"] == ["hwpx", "pptx"]

    @patch("react_system.tools.document_planner.get_examples_for_template", new_callable=AsyncMock)
    @patch("react_system.tools.document_planner.get_template_detail", new_callable=AsyncMock)
    def test_should_return_error_when_template_not_found(self, mock_detail, mock_examples):
        from react_system.tools.document_planner import plan_document

        mock_detail.return_value = {
            "status": "error",
            "message": "양식을 찾을 수 없습니다: tpl-999",
        }

        result = _run(plan_document(
            user_request="보고서",
            template_id="tpl-999",
        ))

        assert result["status"] == "error"
        assert "찾을 수 없습니다" in result["message"]


# ─── 예시 매핑 테스트 ───


class TestPlanDocumentExampleMapping:
    """예시 문서를 섹션에 매핑하는 로직 테스트."""

    @patch("react_system.tools.document_planner.get_examples_for_template", new_callable=AsyncMock)
    @patch("react_system.tools.document_planner.get_template_detail", new_callable=AsyncMock)
    def test_should_include_example_content_in_section_plan(self, mock_detail, mock_examples):
        from react_system.tools.document_planner import plan_document

        mock_detail.return_value = {
            "status": "success",
            "template": _sample_template(id_="tpl-001"),
            "sections": [
                _sample_section(id_="sec-001", title="1. 선박 정보"),
            ],
        }
        mock_examples.return_value = {
            "status": "success",
            "examples": [
                _sample_example(id_="ex-001", content="잘 쓴 예시 내용 A"),
                _sample_example(id_="ex-002", content="잘 쓴 예시 내용 B"),
            ],
            "total": 2,
        }

        result = _run(plan_document(
            user_request="보고서",
            template_id="tpl-001",
        ))

        section = result["plan"]["sections"][0]
        # 예시가 섹션별 분리되지 않으면 전체 content를 각 섹션에 전달
        assert len(section["examples"]) >= 1

    @patch("react_system.tools.document_planner.get_examples_for_template", new_callable=AsyncMock)
    @patch("react_system.tools.document_planner.get_template_detail", new_callable=AsyncMock)
    def test_should_limit_examples_to_5(self, mock_detail, mock_examples):
        from react_system.tools.document_planner import plan_document

        mock_detail.return_value = {
            "status": "success",
            "template": _sample_template(id_="tpl-001"),
            "sections": [
                _sample_section(id_="sec-001", title="1. 선박 정보"),
            ],
        }
        # 8개 예시 반환
        many_examples = [
            _sample_example(id_=f"ex-{i}", content=f"예시 {i}")
            for i in range(8)
        ]
        mock_examples.return_value = {
            "status": "success",
            "examples": many_examples,
            "total": 8,
        }

        result = _run(plan_document(
            user_request="보고서",
            template_id="tpl-001",
        ))

        section = result["plan"]["sections"][0]
        # 최대 5개로 제한
        assert len(section["examples"]) <= 5

    @patch("react_system.tools.document_planner.get_examples_for_template", new_callable=AsyncMock)
    @patch("react_system.tools.document_planner.get_template_detail", new_callable=AsyncMock)
    def test_should_pass_empty_examples_when_none_found(self, mock_detail, mock_examples):
        from react_system.tools.document_planner import plan_document

        mock_detail.return_value = {
            "status": "success",
            "template": _sample_template(id_="tpl-001"),
            "sections": [
                _sample_section(id_="sec-001", title="1. 선박 정보"),
            ],
        }
        mock_examples.return_value = {
            "status": "success",
            "examples": [],
            "total": 0,
        }

        result = _run(plan_document(
            user_request="보고서",
            template_id="tpl-001",
        ))

        section = result["plan"]["sections"][0]
        assert section["examples"] == []


# ─── example_ids 필터링 테스트 ───


class TestPlanDocumentExampleIdFiltering:
    """example_ids가 지정되었을 때 해당 예시만 사용하는지 테스트."""

    @patch("react_system.tools.document_planner.get_examples_for_template", new_callable=AsyncMock)
    @patch("react_system.tools.document_planner.get_template_detail", new_callable=AsyncMock)
    def test_should_filter_examples_by_example_ids(self, mock_detail, mock_examples):
        from react_system.tools.document_planner import plan_document

        mock_detail.return_value = {
            "status": "success",
            "template": _sample_template(id_="tpl-001"),
            "sections": [
                _sample_section(id_="sec-001", title="1. 선박 정보"),
            ],
        }
        mock_examples.return_value = {
            "status": "success",
            "examples": [
                _sample_example(id_="ex-001", content="예시 1"),
                _sample_example(id_="ex-002", content="예시 2"),
                _sample_example(id_="ex-003", content="예시 3"),
            ],
            "total": 3,
        }

        result = _run(plan_document(
            user_request="보고서",
            template_id="tpl-001",
            example_ids=["ex-001", "ex-003"],
        ))

        section = result["plan"]["sections"][0]
        # example_ids로 필터링하면 ex-001, ex-003의 content만 포함
        assert len(section["examples"]) == 2
        assert "예시 1" in section["examples"]
        assert "예시 3" in section["examples"]
        assert "예시 2" not in section["examples"]

    @patch("react_system.tools.document_planner.get_examples_for_template", new_callable=AsyncMock)
    @patch("react_system.tools.document_planner.get_template_detail", new_callable=AsyncMock)
    def test_should_use_all_examples_when_example_ids_is_none(self, mock_detail, mock_examples):
        from react_system.tools.document_planner import plan_document

        mock_detail.return_value = {
            "status": "success",
            "template": _sample_template(id_="tpl-001"),
            "sections": [
                _sample_section(id_="sec-001", title="1. 선박 정보"),
            ],
        }
        mock_examples.return_value = {
            "status": "success",
            "examples": [
                _sample_example(id_="ex-001", content="예시 1"),
                _sample_example(id_="ex-002", content="예시 2"),
            ],
            "total": 2,
        }

        result = _run(plan_document(
            user_request="보고서",
            template_id="tpl-001",
            example_ids=None,
        ))

        section = result["plan"]["sections"][0]
        assert len(section["examples"]) == 2


# ─── 참고문서 매핑 테스트 ───


class TestPlanDocumentReferenceContent:
    """참고문서를 섹션에 매핑하는 로직 테스트."""

    @patch("react_system.tools.document_planner.get_examples_for_template", new_callable=AsyncMock)
    @patch("react_system.tools.document_planner.get_template_detail", new_callable=AsyncMock)
    def test_should_include_reference_content_in_each_section(self, mock_detail, mock_examples):
        from react_system.tools.document_planner import plan_document

        mock_detail.return_value = {
            "status": "success",
            "template": _sample_template(id_="tpl-001"),
            "sections": [
                _sample_section(id_="sec-001", title="1. 선박 정보"),
                _sample_section(id_="sec-002", title="2. 점검 항목"),
            ],
        }
        mock_examples.return_value = {
            "status": "success",
            "examples": [],
            "total": 0,
        }

        ref_content = "2024년 선박 안전 점검 가이드라인 내용..."
        result = _run(plan_document(
            user_request="보고서",
            template_id="tpl-001",
            reference_content=ref_content,
        ))

        # 참고문서 전체가 각 섹션에 동일하게 전달
        for section in result["plan"]["sections"]:
            assert section["reference_content"] == ref_content

    @patch("react_system.tools.document_planner.get_examples_for_template", new_callable=AsyncMock)
    @patch("react_system.tools.document_planner.get_template_detail", new_callable=AsyncMock)
    def test_should_set_empty_reference_when_none_provided(self, mock_detail, mock_examples):
        from react_system.tools.document_planner import plan_document

        mock_detail.return_value = {
            "status": "success",
            "template": _sample_template(id_="tpl-001"),
            "sections": [
                _sample_section(id_="sec-001", title="1. 선박 정보"),
            ],
        }
        mock_examples.return_value = {
            "status": "success",
            "examples": [],
            "total": 0,
        }

        result = _run(plan_document(
            user_request="보고서",
            template_id="tpl-001",
        ))

        section = result["plan"]["sections"][0]
        assert section["reference_content"] == ""

    @patch("react_system.tools.document_planner.get_examples_for_template", new_callable=AsyncMock)
    @patch("react_system.tools.document_planner.get_template_detail", new_callable=AsyncMock)
    def test_should_include_reference_summary_in_plan(self, mock_detail, mock_examples):
        from react_system.tools.document_planner import plan_document

        mock_detail.return_value = {
            "status": "success",
            "template": _sample_template(id_="tpl-001"),
            "sections": [],
        }
        mock_examples.return_value = {
            "status": "success",
            "examples": [],
            "total": 0,
        }

        ref_content = "참고문서 전체 내용이 여기에 들어갑니다."
        result = _run(plan_document(
            user_request="보고서",
            template_id="tpl-001",
            reference_content=ref_content,
        ))

        assert result["plan"]["reference_summary"] == ref_content


# ─── doc_type 추출 테스트 ───


class TestPlanDocumentDocType:
    """doc_type 필드가 양식 카테고리에서 올바르게 추출되는지 테스트."""

    @patch("react_system.tools.document_planner.get_examples_for_template", new_callable=AsyncMock)
    @patch("react_system.tools.document_planner.get_template_detail", new_callable=AsyncMock)
    def test_should_use_template_category_as_doc_type(self, mock_detail, mock_examples):
        from react_system.tools.document_planner import plan_document

        mock_detail.return_value = {
            "status": "success",
            "template": _sample_template(id_="tpl-001", category="안전"),
            "sections": [],
        }
        mock_examples.return_value = {
            "status": "success",
            "examples": [],
            "total": 0,
        }

        result = _run(plan_document(
            user_request="보고서",
            template_id="tpl-001",
        ))

        assert result["plan"]["doc_type"] == "안전"
