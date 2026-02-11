"""관리자 API 라우터 — 문서 업로드, OCR, RAG 파이프라인 관리"""

import os
import secrets
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Header

from db import pool
from ocr import extract_text
from rag import chunk_text, store_chunks

router = APIRouter(prefix="/admin", tags=["admin"])

# 세션 토큰 저장소 (메모리)
_sessions: set[str] = set()

UPLOAD_DIR = Path("/tmp/uploads")
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def _get_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in (".jpg", ".jpeg", ".png"):
        return "image"
    raise ValueError(f"지원하지 않는 파일 형식: {ext}")


async def verify_token(authorization: str = Header(None)):
    """세션 토큰 검증 의존성."""
    if not authorization:
        raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다")
    token = authorization.replace("Bearer ", "")
    if token not in _sessions:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")
    return token


# --- 로그인 ---

@router.post("/login")
async def admin_login(body: dict):
    password = body.get("password", "")
    admin_pw = os.environ.get("ADMIN_PASSWORD", "")
    if not admin_pw or password != admin_pw:
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다")
    token = secrets.token_hex(32)
    _sessions.add(token)
    return {"token": token}


# --- 문서 목록 ---

@router.get("/documents")
async def list_documents(_=Depends(verify_token)):
    if not pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, filename, file_type, status, error_msg, created_at FROM documents ORDER BY id DESC"
        )
    return [
        {
            "id": row["id"],
            "filename": row["filename"],
            "file_type": row["file_type"],
            "status": row["status"],
            "error_msg": row["error_msg"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]


# --- 문서 상세 ---

@router.get("/documents/{doc_id}")
async def get_document(doc_id: int, _=Depends(verify_token)):
    if not pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with pool.acquire() as conn:
        doc = await conn.fetchrow("SELECT * FROM documents WHERE id = $1", doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")
        chunks = await conn.fetch(
            "SELECT id, chunk_index, chunk_text FROM document_chunks WHERE document_id = $1 ORDER BY chunk_index",
            doc_id,
        )
    return {
        "id": doc["id"],
        "filename": doc["filename"],
        "file_type": doc["file_type"],
        "status": doc["status"],
        "error_msg": doc["error_msg"],
        "raw_text": doc["raw_text"],
        "created_at": doc["created_at"].isoformat() if doc["created_at"] else None,
        "chunks": [
            {"id": c["id"], "chunk_index": c["chunk_index"], "chunk_text": c["chunk_text"]}
            for c in chunks
        ],
    }


# --- 파일 업로드 + 자동 처리 ---

@router.post("/upload")
async def upload_document(file: UploadFile = File(...), _=Depends(verify_token)):
    if not pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    # 파일 확장자 검증
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 파일 형식: {ext}")

    file_type = _get_file_type(file.filename)

    # DB에 문서 레코드 생성 (pending)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO documents (filename, file_type, status) VALUES ($1, $2, 'processing') RETURNING id",
            file.filename,
            file_type,
        )
    doc_id = row["id"]

    # 임시 파일 저장
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOAD_DIR / f"{doc_id}_{file.filename}"
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        await _update_doc_status(doc_id, "error", str(e))
        raise HTTPException(status_code=500, detail=f"파일 저장 실패: {e}")

    # OCR → 청킹 → 임베딩 처리
    try:
        # 1. 텍스트 추출
        raw_text = extract_text(str(file_path), file_type)
        if not raw_text.strip():
            await _update_doc_status(doc_id, "error", "텍스트를 추출할 수 없습니다")
            return {"id": doc_id, "status": "error", "error_msg": "텍스트를 추출할 수 없습니다"}

        # 2. raw_text 저장
        async with pool.acquire() as conn:
            await conn.execute("UPDATE documents SET raw_text = $1 WHERE id = $2", raw_text, doc_id)

        # 3. 청킹
        chunks = chunk_text(raw_text)
        if not chunks:
            await _update_doc_status(doc_id, "error", "청크를 생성할 수 없습니다")
            return {"id": doc_id, "status": "error", "error_msg": "청크를 생성할 수 없습니다"}

        # 4. 임베딩 + DB 저장
        await store_chunks(doc_id, chunks)

        # 5. 완료
        await _update_doc_status(doc_id, "done", None)

        return {"id": doc_id, "status": "done", "chunks_count": len(chunks)}

    except Exception as e:
        print(f"문서 처리 오류 (doc_id={doc_id}): {e}", flush=True)
        await _update_doc_status(doc_id, "error", str(e))
        return {"id": doc_id, "status": "error", "error_msg": str(e)}
    finally:
        # 임시 파일 삭제
        if file_path.exists():
            file_path.unlink()


# --- 문서 삭제 ---

@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: int, _=Depends(verify_token)):
    if not pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM documents WHERE id = $1", doc_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")
    return {"message": "삭제 완료"}


# --- 유틸 ---

async def _update_doc_status(doc_id: int, status: str, error_msg: str | None):
    if not pool:
        return
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE documents SET status = $1, error_msg = $2 WHERE id = $3",
            status,
            error_msg,
            doc_id,
        )
