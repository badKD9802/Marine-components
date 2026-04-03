"""
Document API 엔드포인트 테스트

문서 다운로드, 상세 조회, 섹션 수정, 세션별 문서 조회를
mock DB + httpx AsyncClient로 검증한다.
"""

import asyncio
import json
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


def _sample_document_meta(
    doc_id="doc_abc123",
    session_id="sess_001",
    title="선박 점검 보고서",
    doc_type="보고서",
    status="draft",
) -> dict:
    """문서 메타데이터 샘플."""
    return {
        "doc_id": doc_id,
        "session_id": session_id,
        "user_id": "",
        "template_id": "tpl-001",
        "title": title,
        "doc_type": doc_type,
        "status": status,
        "created_at": "2026-04-03T00:00:00+00:00",
        "updated_at": "2026-04-03T00:00:00+00:00",
    }


def _sample_section(
    section_index=0,
    section_title="추진 배경",
    version=1,
) -> dict:
    """섹션 샘플 (DB 행 형태)."""
    return {
        "id": section_index + 1,
        "doc_id": "doc_abc123",
        "section_index": section_index,
        "section_title": section_title,
        "content": {
            "section_id": f"sec_{section_index:02d}",
            "section_title": section_title,
            "elements": [
                {"type": "paragraph", "content": {"text": "본문 내용입니다."}},
            ],
        },
        "version": version,
        "updated_at": "2026-04-03T00:00:00+00:00",
    }


def _make_test_app():
    """테스트용 FastAPI 앱 생성 (document_api 라우터만 포함)."""
    from fastapi import FastAPI
    from document_api import router

    app = FastAPI()
    app.include_router(router)
    return app


# ─── 테스트 1: 문서 상세 조회 (GET /{doc_id}) ───


class TestGetDocumentDetail:
    """문서 상세 조회 엔드포인트 검증"""

    @patch("document_api.document_db")
    def test_should_return_document_with_sections(self, mock_db):
        """문서가 존재하면 메타데이터 + 섹션 목록을 반환해야 한다."""
        import httpx
        mock_db.get_document = AsyncMock(return_value=_sample_document_meta())
        mock_db.get_sections = AsyncMock(return_value=[
            _sample_section(0, "추진 배경"),
            _sample_section(1, "사업 개요"),
        ])

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/documents/doc_abc123")
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        data = resp.json()
        assert data["doc_id"] == "doc_abc123"
        assert data["title"] == "선박 점검 보고서"
        assert len(data["sections"]) == 2

    @patch("document_api.document_db")
    def test_should_return_404_when_document_not_found(self, mock_db):
        """문서가 없으면 404를 반환해야 한다."""
        import httpx
        mock_db.get_document = AsyncMock(return_value=None)

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/documents/doc_nonexistent")
            return resp

        resp = _run(_test())
        assert resp.status_code == 404


# ─── 테스트 2: 세션으로 문서 조회 (GET /by-session/{session_id}) ───


class TestGetDocumentBySession:
    """세션 ID로 문서 조회 검증"""

    @patch("document_api.document_db")
    def test_should_return_document_for_valid_session(self, mock_db):
        """세션에 문서가 있으면 문서 정보를 반환해야 한다."""
        import httpx
        mock_db.get_document_by_session = AsyncMock(
            return_value=_sample_document_meta(session_id="sess_001")
        )
        mock_db.get_sections = AsyncMock(return_value=[
            _sample_section(0, "추진 배경"),
        ])

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/documents/by-session/sess_001")
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "sess_001"

    @patch("document_api.document_db")
    def test_should_return_404_when_session_has_no_document(self, mock_db):
        """세션에 문서가 없으면 404를 반환해야 한다."""
        import httpx
        mock_db.get_document_by_session = AsyncMock(return_value=None)

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/documents/by-session/sess_nonexistent")
            return resp

        resp = _run(_test())
        assert resp.status_code == 404


# ─── 테스트 3: 문서 다운로드 (GET /{doc_id}/download) ───


class TestDownloadDocument:
    """문서 파일 다운로드 검증"""

    @patch("document_api.build_hwpx")
    @patch("document_api.document_db")
    def test_should_return_file_for_hwpx_format(self, mock_db, mock_build):
        """hwpx 형식으로 다운로드 시 파일을 반환해야 한다."""
        import httpx
        import tempfile

        mock_db.get_document = AsyncMock(
            return_value=_sample_document_meta(title="선박 점검 보고서")
        )
        mock_db.get_sections = AsyncMock(return_value=[
            _sample_section(0, "추진 배경"),
        ])

        # 임시 파일 생성 (Builder 결과 시뮬레이션)
        tmp = tempfile.NamedTemporaryFile(suffix=".hwpx", delete=False)
        tmp.write(b"fake hwpx content")
        tmp.close()

        mock_build.return_value = {
            "status": "success",
            "file_path": tmp.name,
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/documents/doc_abc123/download?format=hwpx")
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        assert "application/hwp+zip" in resp.headers.get("content-type", "")

        # 임시 파일 정리
        os.unlink(tmp.name)

    @patch("document_api.build_pptx")
    @patch("document_api.document_db")
    def test_should_return_file_for_pptx_format(self, mock_db, mock_build):
        """pptx 형식으로 다운로드 시 파일을 반환해야 한다."""
        import httpx
        import tempfile

        mock_db.get_document = AsyncMock(
            return_value=_sample_document_meta(title="발표 자료")
        )
        mock_db.get_sections = AsyncMock(return_value=[
            _sample_section(0, "슬라이드 1"),
        ])

        tmp = tempfile.NamedTemporaryFile(suffix=".pptx", delete=False)
        tmp.write(b"fake pptx content")
        tmp.close()

        mock_build.return_value = {
            "status": "success",
            "file_path": tmp.name,
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/documents/doc_abc123/download?format=pptx")
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        assert "presentationml" in resp.headers.get("content-type", "")

        os.unlink(tmp.name)

    @patch("document_api.build_xlsx")
    @patch("document_api.document_db")
    def test_should_return_file_for_xlsx_format(self, mock_db, mock_build):
        """xlsx 형식으로 다운로드 시 파일을 반환해야 한다."""
        import httpx
        import tempfile

        mock_db.get_document = AsyncMock(
            return_value=_sample_document_meta(title="데이터 시트")
        )
        mock_db.get_sections = AsyncMock(return_value=[
            _sample_section(0, "데이터"),
        ])

        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        tmp.write(b"fake xlsx content")
        tmp.close()

        mock_build.return_value = {
            "status": "success",
            "file_path": tmp.name,
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/documents/doc_abc123/download?format=xlsx")
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers.get("content-type", "")

        os.unlink(tmp.name)

    @patch("document_api.document_db")
    def test_should_return_400_for_invalid_format(self, mock_db):
        """지원하지 않는 형식이면 400을 반환해야 한다."""
        import httpx
        mock_db.get_document = AsyncMock(
            return_value=_sample_document_meta()
        )

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/documents/doc_abc123/download?format=pdf")
            return resp

        resp = _run(_test())
        assert resp.status_code == 400

    @patch("document_api.document_db")
    def test_should_return_404_when_document_not_found_for_download(self, mock_db):
        """문서가 없으면 다운로드 시 404를 반환해야 한다."""
        import httpx
        mock_db.get_document = AsyncMock(return_value=None)

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/documents/doc_nonexistent/download")
            return resp

        resp = _run(_test())
        assert resp.status_code == 404

    @patch("document_api.build_hwpx")
    @patch("document_api.document_db")
    def test_should_return_500_when_builder_fails(self, mock_db, mock_build):
        """Builder가 실패하면 500을 반환해야 한다."""
        import httpx

        mock_db.get_document = AsyncMock(
            return_value=_sample_document_meta()
        )
        mock_db.get_sections = AsyncMock(return_value=[
            _sample_section(0, "추진 배경"),
        ])
        mock_build.return_value = {
            "status": "error",
            "message": "빌드 중 오류 발생",
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/documents/doc_abc123/download?format=hwpx")
            return resp

        resp = _run(_test())
        assert resp.status_code == 500


# ─── 테스트 4: 섹션 수정 (POST /{doc_id}/sections/{section_index}/revise) ───


class TestReviseSection:
    """섹션 수정 엔드포인트 검증"""

    @patch("document_api.document_db")
    @patch("document_api.write_section")
    def test_should_revise_section_and_return_updated(self, mock_write, mock_db):
        """기존 섹션에 수정 지시를 보내면 수정된 섹션을 반환해야 한다."""
        import httpx

        existing_section = _sample_section(0, "추진 배경", version=1)
        mock_db.get_document = AsyncMock(return_value=_sample_document_meta())
        mock_db.get_section = AsyncMock(return_value=existing_section)
        mock_db.save_section = AsyncMock(return_value=1)

        revised_content = {
            "section_id": "sec_00",
            "section_title": "추진 배경",
            "elements": [
                {"type": "table", "content": {
                    "columns": [{"name": "항목"}, {"name": "수치"}],
                    "rows": [["매출", "100억"]],
                }},
            ],
        }
        mock_write.return_value = {
            "status": "success",
            "section": revised_content,
            "message": "섹션 '추진 배경' 생성 완료",
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/documents/doc_abc123/sections/0/revise",
                    json={"instruction": "표로 바꿔주고 수치 강조해줘"},
                )
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        data = resp.json()
        assert data["section"]["elements"][0]["type"] == "table"

    @patch("document_api.document_db")
    def test_should_return_404_when_document_not_found_for_revise(self, mock_db):
        """문서가 없으면 수정 시 404를 반환해야 한다."""
        import httpx
        mock_db.get_document = AsyncMock(return_value=None)

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/documents/doc_nonexistent/sections/0/revise",
                    json={"instruction": "수정해줘"},
                )
            return resp

        resp = _run(_test())
        assert resp.status_code == 404

    @patch("document_api.document_db")
    def test_should_return_404_when_section_not_found(self, mock_db):
        """섹션이 없으면 404를 반환해야 한다."""
        import httpx
        mock_db.get_document = AsyncMock(return_value=_sample_document_meta())
        mock_db.get_section = AsyncMock(return_value=None)

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/documents/doc_abc123/sections/99/revise",
                    json={"instruction": "수정해줘"},
                )
            return resp

        resp = _run(_test())
        assert resp.status_code == 404

    @patch("document_api.document_db")
    @patch("document_api.write_section")
    def test_should_return_500_when_writer_fails(self, mock_write, mock_db):
        """Writer가 실패하면 500을 반환해야 한다."""
        import httpx

        mock_db.get_document = AsyncMock(return_value=_sample_document_meta())
        mock_db.get_section = AsyncMock(return_value=_sample_section(0, "추진 배경"))
        mock_write.return_value = {
            "status": "error",
            "message": "LLM 호출 실패",
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/documents/doc_abc123/sections/0/revise",
                    json={"instruction": "수정해줘"},
                )
            return resp

        resp = _run(_test())
        assert resp.status_code == 500

    @patch("document_api.document_db")
    @patch("document_api.write_section")
    def test_should_save_revised_section_to_db(self, mock_write, mock_db):
        """수정 성공 시 DB에 새 버전으로 저장해야 한다."""
        import httpx

        existing_section = _sample_section(0, "추진 배경", version=2)
        mock_db.get_document = AsyncMock(return_value=_sample_document_meta())
        mock_db.get_section = AsyncMock(return_value=existing_section)
        mock_db.save_section = AsyncMock(return_value=1)

        revised_content = {
            "section_id": "sec_00",
            "section_title": "추진 배경",
            "elements": [
                {"type": "paragraph", "content": {"text": "수정된 내용"}},
            ],
        }
        mock_write.return_value = {
            "status": "success",
            "section": revised_content,
            "message": "섹션 '추진 배경' 생성 완료",
        }

        app = _make_test_app()

        async def _test():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/documents/doc_abc123/sections/0/revise",
                    json={"instruction": "내용 수정해줘"},
                )
            return resp

        resp = _run(_test())
        assert resp.status_code == 200
        # save_section이 호출되었는지 확인
        mock_db.save_section.assert_called_once()
        call_kwargs = mock_db.save_section.call_args
        assert call_kwargs.kwargs["doc_id"] == "doc_abc123"
        assert call_kwargs.kwargs["section_index"] == 0
