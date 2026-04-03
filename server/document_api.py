"""
문서 다운로드, 섹션 조회, 섹션 수정 API 엔드포인트

생성된 문서의 파일 다운로드, 상세 조회, 섹션 개별 수정을 제공한다.
"""

import json
import logging
import tempfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from react_system import document_db
from react_system.document_schema import DocumentOutput, SectionOutput
from react_system.tools.document_writer import write_section
from react_system.tools.hwpx_document_builder import build_hwpx
from react_system.tools.pptx_builder import build_pptx
from react_system.tools.xlsx_builder import build_xlsx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

# 지원 포맷 → media_type 매핑
_FORMAT_MEDIA_TYPES = {
    "hwpx": "application/hwp+zip",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

# 지원 포맷 → Builder 함수 이름 매핑 (런타임 조회용)
_FORMAT_BUILDER_NAMES = {
    "hwpx": "build_hwpx",
    "pptx": "build_pptx",
    "xlsx": "build_xlsx",
}


def _get_builder(format: str):
    """포맷에 해당하는 Builder 함수를 런타임에 조회한다."""
    import sys
    module = sys.modules[__name__]
    return getattr(module, _FORMAT_BUILDER_NAMES[format])


class ReviseRequest(BaseModel):
    """섹션 수정 요청"""
    instruction: str  # "표로 바꿔주고 수치 강조해줘"


# ─── 세션으로 문서 조회 (경로 우선순위를 위해 먼저 정의) ───


@router.get("/by-session/{session_id}")
async def get_document_by_session(session_id: str):
    """세션 ID로 최신 문서 조회. 새로고침 복원용."""
    doc = await document_db.get_document_by_session(session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="해당 세션의 문서가 없습니다.")

    sections = await document_db.get_sections(doc["doc_id"])

    return {
        **doc,
        "sections": sections,
    }


# ─── 문서 상세 조회 ───


@router.get("/{doc_id}")
async def get_document_detail(doc_id: str):
    """문서 메타데이터 + 섹션 목록 반환. 새로고침 시 문서 상태 복원용."""
    doc = await document_db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

    sections = await document_db.get_sections(doc_id)

    return {
        **doc,
        "sections": sections,
    }


# ─── 문서 다운로드 ───


@router.get("/{doc_id}/download")
async def download_document(doc_id: str, format: str = "hwpx"):
    """
    문서 파일 다운로드.

    1. document_db.get_document(doc_id) → 문서 메타데이터
    2. document_db.get_sections(doc_id) → 섹션 목록
    3. 섹션들을 DocumentOutput으로 조립
    4. Builder(format)로 파일 생성
    5. FileResponse로 반환

    format: hwpx | pptx | xlsx
    """
    # 문서 조회
    doc = await document_db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

    # 포맷 검증
    if format not in _FORMAT_BUILDER_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 형식입니다: {format}. 지원 형식: {', '.join(_FORMAT_BUILDER_NAMES.keys())}",
        )

    # 섹션 조회
    sections = await document_db.get_sections(doc_id)

    # DocumentOutput 조립
    section_outputs = []
    for sec in sections:
        content = sec.get("content", {})
        if isinstance(content, str):
            content = json.loads(content)
        section_outputs.append(SectionOutput(**content))

    doc_output = DocumentOutput(
        title=doc.get("title", ""),
        doc_type=doc.get("doc_type", ""),
        sections=section_outputs,
    )

    # Builder 호출
    builder = _get_builder(format)
    result = await builder(doc_output)

    if result.get("status") != "success":
        raise HTTPException(
            status_code=500,
            detail=f"파일 생성 실패: {result.get('message', '알 수 없는 오류')}",
        )

    file_path = result["file_path"]
    media_type = _FORMAT_MEDIA_TYPES[format]
    filename = f"{doc.get('title', 'document')}.{format}"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
    )


# ─── 섹션 수정 ───


@router.post("/{doc_id}/sections/{section_index}/revise")
async def revise_section(doc_id: str, section_index: int, req: ReviseRequest):
    """
    특정 섹션 수정.

    1. 문서 존재 확인
    2. 기존 섹션 조회 (document_db.get_section)
    3. write_section() 호출 (기존 내용 + 수정 지시)
    4. document_db.save_section()으로 저장
    5. 수정된 섹션 반환
    """
    # 문서 존재 확인
    doc = await document_db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

    # 기존 섹션 조회
    existing = await document_db.get_section(doc_id, section_index)
    if not existing:
        raise HTTPException(status_code=404, detail="섹션을 찾을 수 없습니다.")

    # 기존 섹션 내용을 참고 자료로 활용
    existing_content = existing.get("content", {})
    if isinstance(existing_content, str):
        existing_content = json.loads(existing_content)

    existing_text = json.dumps(existing_content, ensure_ascii=False)

    # Writer LLM 호출 (기존 내용 + 수정 지시)
    instruction = f"""기존 섹션 내용을 아래 지시에 따라 수정하세요.

[기존 내용]
{existing_text}

[수정 지시]
{req.instruction}"""

    result = await write_section(
        section_index=section_index,
        section_title=existing.get("section_title", ""),
        instruction=instruction,
        template_content="",
        examples=[],
        reference_content=existing_text,
    )

    if result.get("status") != "success":
        raise HTTPException(
            status_code=500,
            detail=f"섹션 수정 실패: {result.get('message', '알 수 없는 오류')}",
        )

    # DB에 수정된 섹션 저장
    revised_section = result["section"]
    await document_db.save_section(
        doc_id=doc_id,
        section_index=section_index,
        section_title=revised_section.get("section_title", existing.get("section_title", "")),
        content=revised_section,
    )

    return {
        "status": "success",
        "section": revised_section,
        "message": f"섹션 '{existing.get('section_title', '')}' 수정 완료",
    }
