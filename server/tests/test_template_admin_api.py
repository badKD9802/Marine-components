"""
양식/예시 관리 API 엔드포인트 테스트

template_admin_api.py의 라우터를 mock 의존성 + httpx AsyncClient로 검증한다.
7개 엔드포인트:
1. POST /api/templates/upload — 양식 업로드
2. POST /api/templates/examples/upload — 예시 업로드
3. GET /api/templates/list — 양식 목록 조회
4. GET /api/templates/categories/list — 카테고리 목록
5. GET /api/templates/{template_id} — 양식 상세 + 예시
6. DELETE /api/templates/{template_id} — 양식 삭제
7. DELETE /api/templates/examples/{example_id} — 예시 삭제
"""

import asyncio
import os
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 프로젝트 모듈
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── 헬퍼 ───


def _run(coro):
    """async 함수를 동기적으로 실행하는 헬퍼."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_test_app():
    """테스트용 FastAPI 앱 생성 (template_admin_api 라우터만 포함)."""
    from fastapi import FastAPI
    from template_admin_api import router

    app = FastAPI()
    app.include_router(router)
    return app


# ─── 테스트 1: 양식 업로드 (POST /upload) ───


class TestUploadTemplateEndpoint:
    """양식 업로드 엔드포인트 검증"""

    @patch("template_admin_api.upload_template")
    @patch("template_admin_api._get_store")
    def test_should_upload_template_with_text_content(self, mock_get_store, mock_upload):
        """텍스트 content로 양식 업로드 시 성공을 반환해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        mock_upload.return_value = {
            "status": "success",
            "template_id": "test001",
            "chunk_count": 3,
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/templates/upload",
                    data={
                        "content": "양식 내용입니다.\n\n두 번째 문단입니다.",
                        "title": "테스트 양식",
                        "category": "보고서",
                        "subcategory": "월간",
                    },
                )
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["template_id"] == "test001"
        assert data["chunk_count"] == 3

    @patch("template_admin_api.upload_template")
    @patch("template_admin_api._get_store")
    def test_should_upload_template_with_file(self, mock_get_store, mock_upload):
        """HWPX 파일로 양식 업로드 시 성공을 반환해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        mock_upload.return_value = {
            "status": "success",
            "template_id": "tpl_auto",
            "chunk_count": 5,
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/templates/upload",
                    data={
                        "title": "파일 양식",
                        "category": "기획서",
                    },
                    files={
                        "file": ("test.hwpx", b"fake hwpx content", "application/octet-stream"),
                    },
                )
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    @patch("template_admin_api._get_store")
    def test_should_return_400_when_no_file_and_no_content(self, mock_get_store):
        """파일도 content도 없으면 400을 반환해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/templates/upload",
                    data={
                        "title": "빈 양식",
                        "category": "보고서",
                    },
                )
            return resp

        resp = _run(_test())
        assert resp.status_code == 400

    @patch("template_admin_api.upload_template")
    @patch("template_admin_api._get_store")
    def test_should_use_custom_template_id_when_provided(self, mock_get_store, mock_upload):
        """template_id가 직접 지정되면 그 값을 사용해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        mock_upload.return_value = {
            "status": "success",
            "template_id": "custom_id",
            "chunk_count": 1,
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/templates/upload",
                    data={
                        "content": "내용",
                        "title": "커스텀 ID",
                        "category": "공문",
                        "template_id": "custom_id",
                    },
                )
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        # upload_template에 전달된 template_id 확인
        call_kwargs = mock_upload.call_args[1]
        assert call_kwargs["template_id"] == "custom_id"

    @patch("template_admin_api.upload_template")
    @patch("template_admin_api._get_store")
    def test_should_return_503_when_milvus_connection_fails(self, mock_get_store, mock_upload):
        """Milvus 연결 실패 시 503을 반환해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        mock_upload.side_effect = ConnectionError("Milvus 연결 실패")

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/templates/upload",
                    data={
                        "content": "내용",
                        "title": "에러 테스트",
                        "category": "보고서",
                    },
                )
            return resp

        resp = _run(_test())
        assert resp.status_code == 503


# ─── 테스트 2: 예시 업로드 (POST /examples/upload) ───


class TestUploadExampleEndpoint:
    """예시 업로드 엔드포인트 검증"""

    @patch("template_admin_api.upload_example")
    @patch("template_admin_api._get_store")
    def test_should_upload_example_with_content(self, mock_get_store, mock_upload):
        """텍스트 content로 예시 업로드 시 성공을 반환해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        mock_upload.return_value = {
            "status": "success",
            "example_id": "ex_pub_abc123",
            "chunk_count": 1,
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/templates/examples/upload",
                    data={
                        "content": "예시 내용입니다.",
                        "title": "예시 제목",
                        "template_id": "tpl001",
                        "category": "보고서",
                    },
                )
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["example_id"] == "ex_pub_abc123"

    @patch("template_admin_api.upload_example")
    @patch("template_admin_api._get_store")
    def test_should_set_private_visibility_with_user_id(self, mock_get_store, mock_upload):
        """user_id가 있으면 upload_example에 user_id를 전달해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        mock_upload.return_value = {
            "status": "success",
            "example_id": "ex_user123_abc",
            "chunk_count": 1,
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/templates/examples/upload",
                    data={
                        "content": "비공개 예시",
                        "title": "비공개 예시 제목",
                        "user_id": "user123",
                    },
                )
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        call_kwargs = mock_upload.call_args[1]
        assert call_kwargs["user_id"] == "user123"

    @patch("template_admin_api._get_store")
    def test_should_return_400_when_no_file_and_no_content_for_example(self, mock_get_store):
        """파일도 content도 없으면 400을 반환해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/templates/examples/upload",
                    data={
                        "title": "빈 예시",
                    },
                )
            return resp

        resp = _run(_test())
        assert resp.status_code == 400


# ─── 테스트 3: 양식 목록 조회 (GET /list) ───


class TestListTemplatesEndpoint:
    """양식 목록 조회 엔드포인트 검증"""

    @patch("template_admin_api.search_templates")
    @patch("template_admin_api._get_store")
    def test_should_search_templates_when_query_given(self, mock_get_store, mock_search):
        """query가 있으면 하이브리드 검색을 해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        mock_search.return_value = {
            "status": "success",
            "templates": [{"id": "tpl-001", "title": "점검 보고서"}],
            "total": 1,
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/templates/list?query=점검")
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert len(data["templates"]) == 1

    @patch("template_admin_api.browse_by_category")
    @patch("template_admin_api._get_store")
    def test_should_browse_by_category_when_no_query(self, mock_get_store, mock_browse):
        """query가 없으면 카테고리 브라우징을 해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        mock_browse.return_value = {
            "status": "success",
            "templates": [
                {"id": "tpl-001", "title": "양식 A", "category": "보고서"},
                {"id": "tpl-002", "title": "양식 B", "category": "보고서"},
            ],
            "total": 2,
            "has_more": False,
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/templates/list?category=보고서")
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    @patch("template_admin_api.browse_by_category")
    @patch("template_admin_api._get_store")
    def test_should_pass_limit_and_offset(self, mock_get_store, mock_browse):
        """limit과 offset이 올바르게 전달되어야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        mock_browse.return_value = {
            "status": "success",
            "templates": [],
            "total": 0,
            "has_more": False,
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/templates/list?limit=5&offset=10")
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        call_kwargs = mock_browse.call_args[1]
        assert call_kwargs["limit"] == 5
        assert call_kwargs["offset"] == 10


# ─── 테스트 4: 양식 상세 조회 (GET /{template_id}) ───


class TestGetTemplateEndpoint:
    """양식 상세 + 예시 조회 엔드포인트 검증"""

    @patch("template_admin_api.get_examples_for_template")
    @patch("template_admin_api.get_template_detail")
    @patch("template_admin_api._get_store")
    def test_should_return_template_with_sections_and_examples(
        self, mock_get_store, mock_detail, mock_examples
    ):
        """양식 상세 정보 + 섹션 + 예시 목록을 반환해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        mock_detail.return_value = {
            "status": "success",
            "template": {"id": "tpl-001", "title": "점검 보고서"},
            "sections": [{"id": "sec-001", "title": "1. 선박 정보"}],
        }
        mock_examples.return_value = {
            "status": "success",
            "examples": [{"id": "ex-001", "title": "예시 1"}],
            "total": 1,
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/templates/tpl-001")
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        data = resp.json()
        assert data["template"]["id"] == "tpl-001"
        assert len(data["sections"]) == 1
        assert len(data["examples"]) == 1

    @patch("template_admin_api.get_template_detail")
    @patch("template_admin_api._get_store")
    def test_should_return_404_when_template_not_found(self, mock_get_store, mock_detail):
        """양식이 없으면 404를 반환해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        mock_detail.return_value = {
            "status": "error",
            "message": "양식을 찾을 수 없습니다: nonexistent",
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/templates/nonexistent")
            return resp

        resp = _run(_test())
        assert resp.status_code == 404


# ─── 테스트 5: 양식 삭제 (DELETE /{template_id}) ───


class TestDeleteTemplateEndpoint:
    """양식 삭제 엔드포인트 검증"""

    @patch("template_admin_api._get_store")
    def test_should_delete_template_and_related_records(self, mock_get_store):
        """양식 + 관련 섹션/예시를 모두 삭제해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_store.query = AsyncMock(return_value=[
            {"id": "tpl_test001"},
            {"id": "tpl_test001_sec00"},
            {"id": "tpl_test001_sec01"},
            {"id": "ex_pub_abc123"},
        ])
        mock_store.delete = AsyncMock()
        mock_get_store.return_value = mock_store

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.delete("/api/templates/test001")
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["deleted_count"] == 4

    @patch("template_admin_api._get_store")
    def test_should_return_404_when_no_records_found_for_delete(self, mock_get_store):
        """삭제할 레코드가 없으면 404를 반환해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_store.query = AsyncMock(return_value=[])
        mock_get_store.return_value = mock_store

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.delete("/api/templates/nonexistent")
            return resp

        resp = _run(_test())
        assert resp.status_code == 404


# ─── 테스트 6: 예시 삭제 (DELETE /examples/{example_id}) ───


class TestDeleteExampleEndpoint:
    """예시 삭제 엔드포인트 검증"""

    @patch("template_admin_api._get_store")
    def test_should_delete_example_by_id(self, mock_get_store):
        """예시 ID로 삭제 시 성공을 반환해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_store.get_by_id = AsyncMock(return_value={
            "id": "ex_pub_abc123",
            "chunk_type": "example",
        })
        mock_store.query = AsyncMock(return_value=[])  # 연결 섹션 없음
        mock_store.delete = AsyncMock()
        mock_get_store.return_value = mock_store

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.delete("/api/templates/examples/ex_pub_abc123")
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    @patch("template_admin_api._get_store")
    def test_should_return_404_when_example_not_found(self, mock_get_store):
        """예시가 없으면 404를 반환해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_store.get_by_id = AsyncMock(return_value=None)
        mock_get_store.return_value = mock_store

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.delete("/api/templates/examples/nonexistent")
            return resp

        resp = _run(_test())
        assert resp.status_code == 404

    @patch("template_admin_api._get_store")
    def test_should_delete_example_with_linked_sections(self, mock_get_store):
        """예시에 연결된 섹션도 함께 삭제해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_store.get_by_id = AsyncMock(return_value={
            "id": "ex_pub_abc123",
            "chunk_type": "example",
        })
        mock_store.query = AsyncMock(return_value=[
            {"id": "ex_pub_abc123_sec00"},
            {"id": "ex_pub_abc123_sec01"},
        ])
        mock_store.delete = AsyncMock()
        mock_get_store.return_value = mock_store

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.delete("/api/templates/examples/ex_pub_abc123")
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        data = resp.json()
        # 예시 1개 + 섹션 2개 = 3개 삭제
        assert data["deleted_count"] == 3


# ─── 테스트 7: 카테고리 목록 (GET /categories/list) ───


class TestListCategoriesEndpoint:
    """카테고리 목록 엔드포인트 검증"""

    @patch("template_admin_api.browse_by_category")
    @patch("template_admin_api._get_store")
    def test_should_return_category_list(self, mock_get_store, mock_browse):
        """등록된 모든 카테고리 목록을 반환해야 한다."""
        import httpx

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store
        mock_browse.return_value = {
            "status": "success",
            "categories": ["보고서", "기획서", "공문"],
            "total": 3,
            "has_more": False,
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/templates/categories/list")
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        data = resp.json()
        assert "보고서" in data["categories"]
        assert "기획서" in data["categories"]
        assert data["total"] == 3
