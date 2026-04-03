"""
양식/예시 업로드 파이프라인

HWPX/텍스트 문서를 파싱하여 Milvus document_templates 컬렉션에 저장한다.
양식(template)과 예시(example) 업로드를 모두 처리한다.

흐름:
1. 파일/텍스트 → 섹션 분할
2. 레코드 생성 (ID 규칙에 따라)
3. TemplateStore.insert()로 Milvus에 저장
"""

import logging
import os
import uuid
from typing import Optional

from react_system.template_store import TemplateStore, get_embedding_fn, get_tokenize_fn

logger = logging.getLogger(__name__)


# ─── HWPX Import 헬퍼 ───


def _import_hwpx_text_extractor():
    """python-hwpx TextExtractor를 import한다. 없으면 None 반환."""
    try:
        from hwpx import TextExtractor
        return TextExtractor
    except ImportError:
        logger.warning("python-hwpx 미설치 — HWPX 파싱 불가, 전체 텍스트로 처리")
        return None


# ─── HWPX 파싱 헬퍼 ───


def parse_hwpx_to_sections(file_path: str) -> list[dict]:
    """
    HWPX 파일을 섹션별로 파싱한다.
    python-hwpx의 TextExtractor를 사용하며, 미설치 시 파일 전체를 단일 섹션으로 처리한다.

    Returns:
        [{"title": "섹션제목", "content": "내용"}, ...]
    """
    TextExtractor = _import_hwpx_text_extractor()

    if TextExtractor is None:
        # python-hwpx 미설치 — 일반 텍스트로 읽기
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="cp949") as f:
                content = f.read()
        return [{"title": "전체", "content": content}]

    # python-hwpx로 섹션별 파싱
    sections = []
    with TextExtractor(file_path) as extractor:
        for idx, section in enumerate(extractor.iter_sections()):
            paragraphs = []
            for para in extractor.iter_paragraphs(section):
                text = para.text()
                if text:
                    paragraphs.append(text)

            section_text = "\n".join(paragraphs).strip()
            if not section_text:
                continue

            sections.append({
                "title": f"섹션 {idx + 1}",
                "content": section_text,
            })

    return sections


# ─── 텍스트 분할 헬퍼 ───


def split_content_to_sections(content: str, max_chars: int = 2000) -> list[dict]:
    """
    긴 텍스트를 섹션으로 자동 분할한다.
    줄바꿈 2개(\\n\\n) 기준으로 분할하고, 각 섹션이 max_chars를 초과하지 않도록 한다.

    Args:
        content: 분할할 텍스트
        max_chars: 섹션당 최대 글자 수

    Returns:
        [{"title": "섹션 N", "content": "내용"}, ...]
    """
    if not content or not content.strip():
        return []

    # 이중 줄바꿈으로 분리
    paragraphs = [p.strip() for p in content.split("\n\n")]
    paragraphs = [p for p in paragraphs if p]

    if not paragraphs:
        return []

    # max_chars 이내로 문단들을 합치기
    sections = []
    current_chunk = ""

    for para in paragraphs:
        candidate = f"{current_chunk}\n\n{para}".strip() if current_chunk else para

        if len(candidate) <= max_chars:
            current_chunk = candidate
        else:
            # 현재 청크가 있으면 먼저 저장
            if current_chunk:
                sections.append(current_chunk)
            current_chunk = para

    # 마지막 청크 저장
    if current_chunk:
        sections.append(current_chunk)

    return [
        {"title": f"섹션 {i + 1}", "content": sec}
        for i, sec in enumerate(sections)
    ]


# ─── 양식 업로드 ───


async def upload_template(
    file_path: str = None,
    template_id: str = "",
    title: str = "",
    category: str = "",
    subcategory: str = "",
    sections: list[dict] = None,
    metadata: dict = None,
    store: TemplateStore = None,
) -> dict:
    """
    양식을 Milvus에 업로드한다.

    1. 양식 전체를 chunk_type="template"으로 저장 (브라우징/검색용)
    2. sections가 제공되면 각 섹션을 chunk_type="section"으로 저장
    3. sections가 없고 file_path가 있으면 파일을 파싱하여 자동 분할

    Args:
        file_path: 업로드할 파일 경로 (HWPX 또는 텍스트)
        template_id: 양식 고유 ID
        title: 양식 제목
        category: 분류 (보고서, 기획서, 공문 등)
        subcategory: 세부 분류
        sections: 수동 섹션 리스트 [{"title": ..., "content": ...}]
        metadata: 추가 메타데이터
        store: TemplateStore 인스턴스

    Returns:
        {"status": "success", "template_id": ..., "chunk_count": ...}
    """
    if store is None:
        store = TemplateStore()

    if metadata is None:
        metadata = {}

    records = []

    # ─── 파일에서 전체 content 읽기 (template 레코드용) ───
    full_content = ""
    if file_path and os.path.exists(file_path):
        file_sections = parse_hwpx_to_sections(file_path)
        full_content = "\n\n".join(s["content"] for s in file_sections)

        # sections가 없으면 파일에서 자동 분할
        if not sections:
            sections = split_content_to_sections(full_content)

    # ─── 1. template 레코드 (양식 전체) ───
    template_record_id = f"tpl_{template_id}"
    template_record = {
        "id": template_record_id,
        "template_id": template_id,
        "chunk_type": "template",
        "parent_id": "",
        "title": title,
        "content": full_content or title,
        "category": category,
        "subcategory": subcategory,
        "visibility": "public",
        "user_id": "",
        "metadata": metadata,
    }
    records.append(template_record)

    # ─── 2. section 레코드 (섹션별) ───
    if sections:
        for idx, sec in enumerate(sections):
            section_record = {
                "id": f"tpl_{template_id}_sec{idx:02d}",
                "template_id": template_id,
                "chunk_type": "section",
                "parent_id": template_record_id,
                "title": sec.get("title", f"섹션 {idx + 1}"),
                "content": sec.get("content", ""),
                "category": category,
                "subcategory": subcategory,
                "visibility": "public",
                "user_id": "",
                "metadata": metadata,
            }
            records.append(section_record)

    # ─── Milvus에 삽입 ───
    embedding_fn = get_embedding_fn()
    tokenize_fn = get_tokenize_fn()

    await store.insert(
        records=records,
        embedding_fn=embedding_fn,
        tokenize_fn=tokenize_fn,
    )

    logger.info(f"양식 업로드 완료: {template_id} ({len(records)}건)")

    return {
        "status": "success",
        "template_id": template_id,
        "chunk_count": len(records),
    }


# ─── 예시 업로드 ───


async def upload_example(
    file_path: str = None,
    content: str = None,
    template_id: str = "",
    title: str = "",
    category: str = "",
    user_id: str = None,
    sections: list[dict] = None,
    metadata: dict = None,
    store: TemplateStore = None,
) -> dict:
    """
    잘 쓴 예시를 Milvus에 업로드한다.

    - chunk_type="example"
    - template_id로 양식과 연결
    - user_id가 있으면 visibility="user:{user_id}" (비공개)
    - user_id가 없으면 visibility="public" (공개)

    Args:
        file_path: 업로드할 파일 경로
        content: 직접 전달할 텍스트 내용
        template_id: 연결할 양식 ID
        title: 예시 제목
        category: 분류
        user_id: 사용자 ID (비공개 설정용)
        sections: 섹션 리스트 [{"title": ..., "content": ...}]
        metadata: 추가 메타데이터
        store: TemplateStore 인스턴스

    Returns:
        {"status": "success", "example_id": ..., "chunk_count": ...}
    """
    if store is None:
        store = TemplateStore()

    if metadata is None:
        metadata = {}

    # ─── 콘텐츠 확보 ───
    if content is None and file_path:
        file_sections = parse_hwpx_to_sections(file_path)
        content = "\n\n".join(s["content"] for s in file_sections)

    if content is None:
        content = ""

    # ─── ID 생성 ───
    owner = user_id if user_id else "pub"
    short_uuid = uuid.uuid4().hex[:8]
    example_id = f"ex_{owner}_{short_uuid}"

    # ─── 가시성 설정 ───
    visibility = f"user:{user_id}" if user_id else "public"
    effective_user_id = user_id or ""

    records = []

    # ─── 1. example 레코드 (예시 전체) ───
    example_record = {
        "id": example_id,
        "template_id": template_id,
        "chunk_type": "example",
        "parent_id": "",
        "title": title,
        "content": content,
        "category": category,
        "subcategory": "",
        "visibility": visibility,
        "user_id": effective_user_id,
        "metadata": metadata,
    }
    records.append(example_record)

    # ─── 2. section 레코드 (섹션별) ───
    if sections:
        for idx, sec in enumerate(sections):
            section_record = {
                "id": f"{example_id}_sec{idx:02d}",
                "template_id": template_id,
                "chunk_type": "section",
                "parent_id": example_id,
                "title": sec.get("title", f"섹션 {idx + 1}"),
                "content": sec.get("content", ""),
                "category": category,
                "subcategory": "",
                "visibility": visibility,
                "user_id": effective_user_id,
                "metadata": metadata,
            }
            records.append(section_record)

    # ─── Milvus에 삽입 ───
    embedding_fn = get_embedding_fn()
    tokenize_fn = get_tokenize_fn()

    await store.insert(
        records=records,
        embedding_fn=embedding_fn,
        tokenize_fn=tokenize_fn,
    )

    logger.info(f"예시 업로드 완료: {example_id} ({len(records)}건)")

    return {
        "status": "success",
        "example_id": example_id,
        "chunk_count": len(records),
    }
