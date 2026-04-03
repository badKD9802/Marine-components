"""
문서 생성 상태 DB 관리

generated_documents: 생성된 문서 메타데이터 (대화 세션과 연결)
document_sections: 각 섹션의 최신 콘텐츠 + 버전 관리
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


async def _get_pool():
    """메인 DB 풀 가져오기."""
    from db import pool
    return pool


# ─── 테이블 생성 ───

async def create_document_tables():
    """문서 생성 관련 테이블 생성."""
    pool = await _get_pool()
    if not pool:
        logger.warning("DB 풀 없음 — 문서 테이블 생성 건너뜀")
        return

    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS generated_documents (
                doc_id VARCHAR(128) PRIMARY KEY,
                session_id VARCHAR(128),
                user_id VARCHAR(64),
                template_id VARCHAR(256),
                title VARCHAR(512) DEFAULT '',
                doc_type VARCHAR(64) DEFAULT '',
                status VARCHAR(16) DEFAULT 'draft',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS document_sections (
                id SERIAL PRIMARY KEY,
                doc_id VARCHAR(128) REFERENCES generated_documents(doc_id) ON DELETE CASCADE,
                section_index INTEGER NOT NULL,
                section_title VARCHAR(512) DEFAULT '',
                content JSONB DEFAULT '{}',
                version INTEGER DEFAULT 1,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        # 인덱스
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_doc_sections_doc_id
            ON document_sections(doc_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_generated_docs_session
            ON generated_documents(session_id)
        """)

    logger.info("문서 생성 테이블 준비 완료")


# ─── 문서 CRUD ───

async def create_document(
    session_id: str,
    template_id: str = "",
    title: str = "",
    doc_type: str = "",
    user_id: str = "",
) -> str:
    """새 문서 레코드 생성. doc_id 반환."""
    pool = await _get_pool()
    if not pool:
        raise RuntimeError("DB 미연결")

    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO generated_documents (doc_id, session_id, user_id, template_id, title, doc_type)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            doc_id, session_id, user_id, template_id, title, doc_type,
        )
    return doc_id


async def get_document(doc_id: str) -> Optional[dict]:
    """문서 메타데이터 조회."""
    pool = await _get_pool()
    if not pool:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM generated_documents WHERE doc_id = $1", doc_id
        )
    if not row:
        return None
    return dict(row)


async def get_document_by_session(session_id: str) -> Optional[dict]:
    """세션 ID로 최신 문서 조회."""
    pool = await _get_pool()
    if not pool:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT * FROM generated_documents
            WHERE session_id = $1
            ORDER BY created_at DESC LIMIT 1""",
            session_id,
        )
    if not row:
        return None
    return dict(row)


async def update_document_status(doc_id: str, status: str):
    """문서 상태 변경 (draft → completed)."""
    pool = await _get_pool()
    if not pool:
        return

    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE generated_documents
            SET status = $1, updated_at = NOW()
            WHERE doc_id = $2""",
            status, doc_id,
        )


# ─── 섹션 CRUD ───

async def save_section(
    doc_id: str,
    section_index: int,
    section_title: str,
    content: dict,
) -> int:
    """섹션 저장 (새로 생성 또는 버전 업데이트). section id 반환."""
    pool = await _get_pool()
    if not pool:
        raise RuntimeError("DB 미연결")

    content_json = json.dumps(content, ensure_ascii=False)

    async with pool.acquire() as conn:
        # 기존 섹션 확인
        existing = await conn.fetchrow(
            """SELECT id, version FROM document_sections
            WHERE doc_id = $1 AND section_index = $2
            ORDER BY version DESC LIMIT 1""",
            doc_id, section_index,
        )

        if existing:
            # 새 버전으로 업데이트
            new_version = existing["version"] + 1
            await conn.execute(
                """UPDATE document_sections
                SET content = $1::jsonb, version = $2,
                    section_title = $3, updated_at = NOW()
                WHERE id = $4""",
                content_json, new_version, section_title, existing["id"],
            )
            return existing["id"]
        else:
            # 새로 생성
            row = await conn.fetchrow(
                """INSERT INTO document_sections
                (doc_id, section_index, section_title, content, version)
                VALUES ($1, $2, $3, $4::jsonb, 1)
                RETURNING id""",
                doc_id, section_index, section_title, content_json,
            )
            return row["id"]


async def get_sections(doc_id: str) -> list[dict]:
    """문서의 모든 섹션 조회 (section_index 순)."""
    pool = await _get_pool()
    if not pool:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM document_sections
            WHERE doc_id = $1
            ORDER BY section_index""",
            doc_id,
        )
    return [dict(row) for row in rows]


async def get_section(doc_id: str, section_index: int) -> Optional[dict]:
    """특정 섹션 조회."""
    pool = await _get_pool()
    if not pool:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT * FROM document_sections
            WHERE doc_id = $1 AND section_index = $2""",
            doc_id, section_index,
        )
    if not row:
        return None
    return dict(row)
