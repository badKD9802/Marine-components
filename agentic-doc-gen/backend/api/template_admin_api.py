"""
양식/예시 관리 API 엔드포인트

관리자가 양식(template)과 예시(example)를 업로드/관리하는 REST API.
Milvus document_templates 컬렉션에 대한 CRUD 작업을 제공한다.
"""

import logging
import os
import tempfile
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from react_system.template_search import (
    browse_by_category,
    get_examples_for_template,
    get_template_detail,
    search_templates,
)
from react_system.template_store import TemplateStore
from react_system.template_upload import (
    parse_hwpx_to_sections,
    split_content_to_sections,
    upload_example,
    upload_template,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/templates", tags=["templates"])

# ─── TemplateStore 싱글톤 ───

_store: TemplateStore | None = None


def _get_store() -> TemplateStore:
    """TemplateStore 싱글톤 인스턴스 반환 (lazy init)."""
    global _store
    if _store is None:
        _store = TemplateStore()
    return _store


# ─── 허용 확장자 ───

ALLOWED_EXTENSIONS = {".hwpx", ".txt", ".md"}


def _validate_extension(filename: str) -> str:
    """파일 확장자 검증. 허용되지 않으면 ValueError 발생."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"지원하지 않는 파일 형식: {ext}. 허용: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    return ext


# ─── 1. 양식 업로드 ───


@router.post("/upload")
async def upload_template_endpoint(
    file: UploadFile = File(None),
    content: str = Form(None),
    title: str = Form(...),
    category: str = Form(...),
    subcategory: str = Form(""),
    template_id: str = Form(None),
):
    """
    양식 업로드.
    - file이 있으면: 임시 파일 저장 → 파싱 → Milvus 저장
    - file 없고 content 있으면: 텍스트 분할 → Milvus 저장
    - 둘 다 없으면: 400 에러
    """
    store = _get_store()

    # template_id 자동 생성
    if not template_id:
        template_id = f"tpl_{uuid.uuid4().hex[:8]}"

    tmp_path = None
    try:
        if file and file.filename:
            # 파일 업로드 처리
            _validate_extension(file.filename)
            suffix = os.path.splitext(file.filename)[1]
            with tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False
            ) as tmp:
                tmp.write(await file.read())
                tmp_path = tmp.name

            result = await upload_template(
                file_path=tmp_path,
                template_id=template_id,
                title=title,
                category=category,
                subcategory=subcategory,
                store=store,
            )
        elif content:
            # 텍스트 콘텐츠 처리
            sections = split_content_to_sections(content)
            result = await upload_template(
                file_path=None,
                template_id=template_id,
                title=title,
                category=category,
                subcategory=subcategory,
                sections=sections,
                store=store,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="파일 또는 텍스트 내용이 필요합니다.",
            )

        return result

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (ConnectionError, OSError) as e:
        logger.error(f"양식 업로드 실패 (연결 오류): {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Milvus 연결 실패: {e}",
        )
    except Exception as e:
        logger.error(f"양식 업로드 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ─── 2. 예시 업로드 ───


@router.post("/examples/upload")
async def upload_example_endpoint(
    file: UploadFile = File(None),
    content: str = Form(None),
    template_id: str = Form(""),
    title: str = Form(...),
    category: str = Form(""),
    user_id: str = Form(None),
):
    """
    예시 문서 업로드.
    - user_id 있으면 visibility="user:{user_id}" (비공개)
    - 없으면 visibility="public" (공개)
    """
    store = _get_store()

    tmp_path = None
    try:
        file_path_arg = None

        if file and file.filename:
            # 파일 업로드 처리
            _validate_extension(file.filename)
            suffix = os.path.splitext(file.filename)[1]
            with tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False
            ) as tmp:
                tmp.write(await file.read())
                tmp_path = tmp.name
            file_path_arg = tmp_path
        elif not content:
            raise HTTPException(
                status_code=400,
                detail="파일 또는 텍스트 내용이 필요합니다.",
            )

        result = await upload_example(
            file_path=file_path_arg,
            content=content,
            template_id=template_id,
            title=title,
            category=category,
            user_id=user_id,
            store=store,
        )

        return result

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (ConnectionError, OSError) as e:
        logger.error(f"예시 업로드 실패 (연결 오류): {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Milvus 연결 실패: {e}",
        )
    except Exception as e:
        logger.error(f"예시 업로드 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ─── 3. 양식 목록 조회 ───


@router.get("/list")
async def list_templates(
    category: str = None,
    query: str = None,
    limit: int = 20,
    offset: int = 0,
):
    """
    양식 목록.
    - query 있으면: 하이브리드 검색 (search_templates)
    - query 없으면: 카테고리 브라우징 (browse_by_category)
    """
    store = _get_store()

    try:
        if query:
            result = await search_templates(
                query=query,
                category=category,
                limit=limit,
                offset=offset,
                store=store,
            )
        else:
            result = await browse_by_category(
                category=category,
                limit=limit,
                offset=offset,
                store=store,
            )

        return result

    except (ConnectionError, OSError) as e:
        logger.error(f"양식 목록 조회 실패 (연결 오류): {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Milvus 연결 실패: {e}",
        )
    except Exception as e:
        logger.error(f"양식 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── 4. 카테고리 목록 ───


@router.get("/categories/list")
async def list_categories():
    """등록된 모든 카테고리 목록 반환."""
    store = _get_store()

    try:
        result = await browse_by_category(
            category=None,
            store=store,
        )
        return result

    except (ConnectionError, OSError) as e:
        logger.error(f"카테고리 목록 조회 실패 (연결 오류): {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Milvus 연결 실패: {e}",
        )
    except Exception as e:
        logger.error(f"카테고리 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── 5. 양식 상세 + 예시 조회 ───


@router.get("/{template_id}")
async def get_template(template_id: str):
    """양식 상세 정보 + 섹션 + 연결된 예시 목록."""
    store = _get_store()

    try:
        detail = await get_template_detail(
            template_id=template_id,
            store=store,
        )

        if detail.get("status") == "error":
            raise HTTPException(
                status_code=404,
                detail=detail.get("message", "양식을 찾을 수 없습니다."),
            )

        examples = await get_examples_for_template(
            template_id=template_id,
            store=store,
        )

        return {
            "template": detail.get("template"),
            "sections": detail.get("sections", []),
            "examples": examples.get("examples", []),
        }

    except HTTPException:
        raise
    except (ConnectionError, OSError) as e:
        logger.error(f"양식 상세 조회 실패 (연결 오류): {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Milvus 연결 실패: {e}",
        )
    except Exception as e:
        logger.error(f"양식 상세 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── 6. 양식 삭제 ───


@router.delete("/{template_id}")
async def delete_template(template_id: str):
    """양식 + 연결된 섹션/예시 전부 삭제."""
    store = _get_store()

    try:
        # template_id로 연결된 모든 레코드 조회
        records = await store.query(
            filter_expr=f'template_id == "{template_id}"',
            limit=10000,
            output_fields=["id"],
        )

        if not records:
            raise HTTPException(
                status_code=404,
                detail=f"양식을 찾을 수 없습니다: {template_id}",
            )

        ids = [r["id"] for r in records]
        await store.delete(ids=ids)

        return {
            "status": "success",
            "template_id": template_id,
            "deleted_count": len(ids),
        }

    except HTTPException:
        raise
    except (ConnectionError, OSError) as e:
        logger.error(f"양식 삭제 실패 (연결 오류): {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Milvus 연결 실패: {e}",
        )
    except Exception as e:
        logger.error(f"양식 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── 7. 예시 삭제 ───


@router.delete("/examples/{example_id}")
async def delete_example(example_id: str):
    """특정 예시 삭제 (연결된 섹션 포함)."""
    store = _get_store()

    try:
        # 예시 레코드 확인
        example = await store.get_by_id(example_id)
        if not example:
            raise HTTPException(
                status_code=404,
                detail=f"예시를 찾을 수 없습니다: {example_id}",
            )

        ids_to_delete = [example_id]

        # 연결된 섹션 조회
        sections = await store.query(
            filter_expr=f'parent_id == "{example_id}" and chunk_type == "section"',
            limit=1000,
            output_fields=["id"],
        )
        ids_to_delete.extend(r["id"] for r in sections)

        await store.delete(ids=ids_to_delete)

        return {
            "status": "success",
            "example_id": example_id,
            "deleted_count": len(ids_to_delete),
        }

    except HTTPException:
        raise
    except (ConnectionError, OSError) as e:
        logger.error(f"예시 삭제 실패 (연결 오류): {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Milvus 연결 실패: {e}",
        )
    except Exception as e:
        logger.error(f"예시 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
