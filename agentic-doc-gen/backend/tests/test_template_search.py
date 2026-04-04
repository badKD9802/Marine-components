"""
양식 검색 API 테스트

TemplateStore를 mock하여 Milvus 연결 없이
search_templates, browse_by_category, get_examples_for_template,
get_template_detail, _build_visibility_filter를 검증한다.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 프로젝트 모듈
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── 헬퍼 ───


def _run(coro):
    """async 함수를 동기적으로 실행하는 헬퍼."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ─── _build_visibility_filter 단위 테스트 ───


class TestBuildVisibilityFilter:
    """visibility 필터 표현식 빌더 테스트."""

    def test_should_return_public_only_when_no_user_id(self):
        from react_system.template_search import _build_visibility_filter

        result = _build_visibility_filter()
        assert result == 'visibility == "public"'

    def test_should_return_public_only_when_user_id_is_none(self):
        from react_system.template_search import _build_visibility_filter

        result = _build_visibility_filter(user_id=None)
        assert result == 'visibility == "public"'

    def test_should_include_user_visibility_when_user_id_given(self):
        from react_system.template_search import _build_visibility_filter

        result = _build_visibility_filter(user_id="user123")
        assert result == 'visibility in ["public", "user:user123"]'

    def test_should_embed_user_id_in_filter_expression(self):
        from react_system.template_search import _build_visibility_filter

        result = _build_visibility_filter(user_id="alice")
        assert "user:alice" in result


# ─── _build_filter_expr 단위 테스트 ───


class TestBuildFilterExpr:
    """복합 필터 표현식 빌더 테스트."""

    def test_should_include_chunk_type(self):
        from react_system.template_search import _build_filter_expr

        result = _build_filter_expr(chunk_type="template")
        assert 'chunk_type == "template"' in result

    def test_should_combine_chunk_type_and_visibility(self):
        from react_system.template_search import _build_filter_expr

        result = _build_filter_expr(chunk_type="template", user_id="u1")
        assert 'chunk_type == "template"' in result
        assert 'visibility in ["public", "user:u1"]' in result
        assert " and " in result

    def test_should_include_category_when_provided(self):
        from react_system.template_search import _build_filter_expr

        result = _build_filter_expr(chunk_type="template", category="안전")
        assert 'category == "안전"' in result

    def test_should_include_template_id_when_provided(self):
        from react_system.template_search import _build_filter_expr

        result = _build_filter_expr(chunk_type="example", template_id="tpl-001")
        assert 'template_id == "tpl-001"' in result

    def test_should_combine_all_conditions(self):
        from react_system.template_search import _build_filter_expr

        result = _build_filter_expr(
            chunk_type="example",
            user_id="u1",
            category="안전",
            template_id="tpl-001",
        )
        assert 'chunk_type == "example"' in result
        assert 'visibility in ["public", "user:u1"]' in result
        assert 'category == "안전"' in result
        assert 'template_id == "tpl-001"' in result
        # 모든 조건이 AND로 결합
        assert result.count(" and ") == 3


# ─── Mock 헬퍼 ───


def _make_mock_store():
    """TemplateStore mock 생성."""
    store = MagicMock()
    store.hybrid_search = AsyncMock(return_value=[])
    store.query = AsyncMock(return_value=[])
    store.get_by_id = AsyncMock(return_value=None)
    return store


def _sample_template(
    id_="tpl-001",
    title="선박 점검 보고서",
    category="안전",
    subcategory="점검",
    score=0.95,
    **extra,
):
    """검색 결과 샘플 양식 레코드."""
    rec = {
        "id": id_,
        "template_id": id_,
        "chunk_type": "template",
        "parent_id": "",
        "title": title,
        "content": "선박 점검 보고서 양식입니다.",
        "category": category,
        "subcategory": subcategory,
        "visibility": "public",
        "user_id": "",
        "metadata": {},
        "created_at": 1700000000,
        "updated_at": 1700000000,
        "score": score,
    }
    rec.update(extra)
    return rec


def _sample_example(
    id_="ex-001",
    template_id="tpl-001",
    title="점검 보고서 예시 1",
    user_id="",
    visibility="public",
):
    """검색 결과 샘플 예시 레코드."""
    return {
        "id": id_,
        "template_id": template_id,
        "chunk_type": "example",
        "parent_id": template_id,
        "title": title,
        "content": "예시 내용입니다.",
        "category": "안전",
        "subcategory": "점검",
        "visibility": visibility,
        "user_id": user_id,
        "metadata": {},
        "created_at": 1700000000,
        "updated_at": 1700000000,
    }


def _sample_section(id_="sec-001", template_id="tpl-001", title="1. 선박 정보"):
    """검색 결과 샘플 섹션 레코드."""
    return {
        "id": id_,
        "template_id": template_id,
        "chunk_type": "section",
        "parent_id": template_id,
        "title": title,
        "content": "선박명, 선박 번호, 점검 일자 등을 기입합니다.",
        "category": "안전",
        "subcategory": "점검",
        "visibility": "public",
        "user_id": "",
        "metadata": {},
        "created_at": 1700000000,
        "updated_at": 1700000000,
    }


# ─── search_templates 테스트 ───


class TestSearchTemplates:
    """하이브리드 검색 API 테스트."""

    def test_should_return_success_status_with_empty_results(self):
        from react_system.template_search import search_templates

        store = _make_mock_store()
        store.hybrid_search = AsyncMock(return_value=[])

        result = _run(search_templates(query="점검 보고서", store=store))

        assert result["status"] == "success"
        assert result["templates"] == []
        assert result["total"] == 0

    def test_should_call_hybrid_search_with_correct_filter(self):
        from react_system.template_search import search_templates

        store = _make_mock_store()
        store.hybrid_search = AsyncMock(return_value=[])

        _run(search_templates(
            query="점검",
            user_id="user123",
            store=store,
        ))

        # hybrid_search가 호출되었는지 확인
        store.hybrid_search.assert_called_once()
        call_kwargs = store.hybrid_search.call_args
        filter_expr = call_kwargs.kwargs.get("filter_expr") or call_kwargs[1].get("filter_expr", "")
        # chunk_type 필터와 visibility 필터가 포함되어야 함
        assert 'chunk_type == "template"' in filter_expr
        assert 'visibility in ["public", "user:user123"]' in filter_expr

    def test_should_include_category_in_filter_when_provided(self):
        from react_system.template_search import search_templates

        store = _make_mock_store()
        store.hybrid_search = AsyncMock(return_value=[])

        _run(search_templates(
            query="보고서",
            category="안전",
            store=store,
        ))

        call_kwargs = store.hybrid_search.call_args
        filter_expr = call_kwargs.kwargs.get("filter_expr") or call_kwargs[1].get("filter_expr", "")
        assert 'category == "안전"' in filter_expr

    def test_should_return_template_list_from_hybrid_search(self):
        from react_system.template_search import search_templates

        store = _make_mock_store()
        hits = [
            _sample_template(id_="tpl-001", title="점검 보고서", score=0.95),
            _sample_template(id_="tpl-002", title="정비 보고서", score=0.80),
        ]
        store.hybrid_search = AsyncMock(return_value=hits)

        result = _run(search_templates(query="보고서", store=store))

        assert result["status"] == "success"
        assert len(result["templates"]) == 2
        assert result["templates"][0]["id"] == "tpl-001"
        assert result["templates"][1]["id"] == "tpl-002"
        assert result["total"] == 2

    def test_should_return_error_on_exception(self):
        from react_system.template_search import search_templates

        store = _make_mock_store()
        store.hybrid_search = AsyncMock(side_effect=Exception("연결 실패"))

        result = _run(search_templates(query="보고서", store=store))

        assert result["status"] == "error"
        assert "연결 실패" in result["message"]

    def test_should_pass_limit_to_hybrid_search(self):
        from react_system.template_search import search_templates

        store = _make_mock_store()
        store.hybrid_search = AsyncMock(return_value=[])

        _run(search_templates(query="보고서", limit=5, store=store))

        call_kwargs = store.hybrid_search.call_args
        limit = call_kwargs.kwargs.get("limit") or call_kwargs[1].get("limit")
        assert limit == 5


# ─── browse_by_category 테스트 ───


class TestBrowseByCategory:
    """카테고리 브라우징 API 테스트."""

    def test_should_return_category_list_when_no_category_given(self):
        """category=None이면 전체 카테고리 목록 반환."""
        from react_system.template_search import browse_by_category

        store = _make_mock_store()
        store.query = AsyncMock(return_value=[
            _sample_template(category="안전"),
            _sample_template(id_="tpl-002", category="정비"),
            _sample_template(id_="tpl-003", category="안전"),
        ])

        result = _run(browse_by_category(store=store))

        assert result["status"] == "success"
        # 중복 제거된 카테고리 목록
        categories = result["categories"]
        assert "안전" in categories
        assert "정비" in categories
        assert len(categories) == 2

    def test_should_return_templates_for_specific_category(self):
        """category 지정 시 해당 카테고리의 양식 목록."""
        from react_system.template_search import browse_by_category

        store = _make_mock_store()
        templates = [
            _sample_template(id_="tpl-001", category="안전"),
            _sample_template(id_="tpl-002", category="안전"),
        ]
        store.query = AsyncMock(return_value=templates)

        result = _run(browse_by_category(category="안전", store=store))

        assert result["status"] == "success"
        assert len(result["templates"]) == 2
        assert result["total"] == 2

    def test_should_include_has_more_flag(self):
        """has_more 플래그 정확성 검증."""
        from react_system.template_search import browse_by_category

        store = _make_mock_store()
        # limit+1 개를 반환하면 has_more=True
        templates = [_sample_template(id_=f"tpl-{i}") for i in range(3)]
        store.query = AsyncMock(return_value=templates)

        result = _run(browse_by_category(category="안전", limit=2, store=store))

        assert result["has_more"] is True
        # 반환되는 templates는 limit개만
        assert len(result["templates"]) == 2

    def test_should_not_have_more_when_results_equal_to_limit(self):
        """결과가 limit 이하이면 has_more=False."""
        from react_system.template_search import browse_by_category

        store = _make_mock_store()
        templates = [_sample_template(id_=f"tpl-{i}") for i in range(2)]
        store.query = AsyncMock(return_value=templates)

        result = _run(browse_by_category(category="안전", limit=5, store=store))

        assert result["has_more"] is False

    def test_should_apply_chunk_type_filter(self):
        """chunk_type='template' 필터가 적용되는지 확인."""
        from react_system.template_search import browse_by_category

        store = _make_mock_store()
        store.query = AsyncMock(return_value=[])

        _run(browse_by_category(category="안전", store=store))

        call_args = store.query.call_args
        filter_expr = call_args.kwargs.get("filter_expr") or call_args[0][0]
        assert 'chunk_type == "template"' in filter_expr

    def test_should_return_error_on_exception(self):
        from react_system.template_search import browse_by_category

        store = _make_mock_store()
        store.query = AsyncMock(side_effect=Exception("DB 오류"))

        result = _run(browse_by_category(store=store))

        assert result["status"] == "error"
        assert "DB 오류" in result["message"]


# ─── get_examples_for_template 테스트 ───


class TestGetExamplesForTemplate:
    """특정 양식의 예시 조회 API 테스트."""

    def test_should_return_empty_examples_when_none_found(self):
        from react_system.template_search import get_examples_for_template

        store = _make_mock_store()
        store.query = AsyncMock(return_value=[])

        result = _run(get_examples_for_template(
            template_id="tpl-001", store=store,
        ))

        assert result["status"] == "success"
        assert result["examples"] == []
        assert result["total"] == 0

    def test_should_filter_by_template_id_and_chunk_type_example(self):
        from react_system.template_search import get_examples_for_template

        store = _make_mock_store()
        store.query = AsyncMock(return_value=[])

        _run(get_examples_for_template(
            template_id="tpl-001", store=store,
        ))

        call_args = store.query.call_args
        filter_expr = call_args.kwargs.get("filter_expr") or call_args[0][0]
        assert 'chunk_type == "example"' in filter_expr
        assert 'template_id == "tpl-001"' in filter_expr

    def test_should_mark_is_mine_for_matching_user_id(self):
        """user_id가 일치하는 예시에는 is_mine=True."""
        from react_system.template_search import get_examples_for_template

        store = _make_mock_store()
        examples = [
            _sample_example(id_="ex-001", user_id="user123", visibility="user:user123"),
            _sample_example(id_="ex-002", user_id="", visibility="public"),
        ]
        store.query = AsyncMock(return_value=examples)

        result = _run(get_examples_for_template(
            template_id="tpl-001",
            user_id="user123",
            store=store,
        ))

        assert result["examples"][0]["is_mine"] is True
        assert result["examples"][1]["is_mine"] is False

    def test_should_sort_user_examples_first(self):
        """내 예시(is_mine=True)가 먼저 나와야 함."""
        from react_system.template_search import get_examples_for_template

        store = _make_mock_store()
        # 의도적으로 public 먼저, user 나중에 배치
        examples = [
            _sample_example(id_="ex-pub", user_id="", visibility="public"),
            _sample_example(id_="ex-mine", user_id="user123", visibility="user:user123"),
        ]
        store.query = AsyncMock(return_value=examples)

        result = _run(get_examples_for_template(
            template_id="tpl-001",
            user_id="user123",
            store=store,
        ))

        # 내 예시가 먼저
        assert result["examples"][0]["id"] == "ex-mine"
        assert result["examples"][0]["is_mine"] is True
        assert result["examples"][1]["id"] == "ex-pub"
        assert result["examples"][1]["is_mine"] is False

    def test_should_return_error_on_exception(self):
        from react_system.template_search import get_examples_for_template

        store = _make_mock_store()
        store.query = AsyncMock(side_effect=Exception("타임아웃"))

        result = _run(get_examples_for_template(
            template_id="tpl-001", store=store,
        ))

        assert result["status"] == "error"
        assert "타임아웃" in result["message"]


# ─── get_template_detail 테스트 ───


class TestGetTemplateDetail:
    """양식 상세 조회 API 테스트."""

    def test_should_return_template_with_sections(self):
        from react_system.template_search import get_template_detail

        store = _make_mock_store()
        tpl = _sample_template(id_="tpl-001", title="점검 보고서")
        sec1 = _sample_section(id_="sec-001", template_id="tpl-001", title="1. 선박 정보")
        sec2 = _sample_section(id_="sec-002", template_id="tpl-001", title="2. 점검 항목")

        store.get_by_id = AsyncMock(return_value=tpl)
        store.query = AsyncMock(return_value=[sec1, sec2])

        result = _run(get_template_detail(template_id="tpl-001", store=store))

        assert result["status"] == "success"
        assert result["template"]["id"] == "tpl-001"
        assert len(result["sections"]) == 2
        assert result["sections"][0]["id"] == "sec-001"

    def test_should_return_error_when_template_not_found(self):
        from react_system.template_search import get_template_detail

        store = _make_mock_store()
        store.get_by_id = AsyncMock(return_value=None)

        result = _run(get_template_detail(template_id="nonexistent", store=store))

        assert result["status"] == "error"
        assert "찾을 수 없습니다" in result["message"]

    def test_should_query_sections_with_correct_filter(self):
        from react_system.template_search import get_template_detail

        store = _make_mock_store()
        tpl = _sample_template(id_="tpl-001")
        store.get_by_id = AsyncMock(return_value=tpl)
        store.query = AsyncMock(return_value=[])

        _run(get_template_detail(template_id="tpl-001", store=store))

        call_args = store.query.call_args
        filter_expr = call_args.kwargs.get("filter_expr") or call_args[0][0]
        assert 'chunk_type == "section"' in filter_expr
        assert 'template_id == "tpl-001"' in filter_expr

    def test_should_return_empty_sections_when_none_exist(self):
        from react_system.template_search import get_template_detail

        store = _make_mock_store()
        tpl = _sample_template(id_="tpl-001")
        store.get_by_id = AsyncMock(return_value=tpl)
        store.query = AsyncMock(return_value=[])

        result = _run(get_template_detail(template_id="tpl-001", store=store))

        assert result["status"] == "success"
        assert result["sections"] == []

    def test_should_return_error_on_exception(self):
        from react_system.template_search import get_template_detail

        store = _make_mock_store()
        store.get_by_id = AsyncMock(side_effect=Exception("네트워크 오류"))

        result = _run(get_template_detail(template_id="tpl-001", store=store))

        assert result["status"] == "error"
        assert "네트워크 오류" in result["message"]
