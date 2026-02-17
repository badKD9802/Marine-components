"""견적문의 게시판 API"""

import hashlib
import secrets
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

import db
from admin import verify_token

router = APIRouter(tags=["inquiry"])


def _hash_password(password: str) -> str:
    """PBKDF2-SHA256으로 비밀번호 해시 (salt 포함)."""
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return salt + ":" + h.hex()


def _verify_password(password: str, stored_hash: str) -> bool:
    """저장된 해시와 비밀번호 비교."""
    parts = stored_hash.split(":", 1)
    if len(parts) != 2:
        return False
    salt, expected = parts
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return h.hex() == expected


# --- 요청 모델 ---

class InquiryCreate(BaseModel):
    author_name: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=4, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=5000)


class InquiryVerify(BaseModel):
    author_name: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class ReplyCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


# --- 공개 엔드포인트 ---

@router.get("/api/inquiries")
async def list_inquiries(page: int = 1, size: int = 10):
    if not db.pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    if size > 50:
        size = 50
    offset = (page - 1) * size
    async with db.pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM inquiries")
        rows = await conn.fetch(
            "SELECT id, author_name, title, status, created_at FROM inquiries ORDER BY id DESC LIMIT $1 OFFSET $2",
            size, offset,
        )
    items = [
        {
            "id": r["id"],
            "author_name": r["author_name"],
            "title": r["title"],
            "status": r["status"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "size": size}


@router.post("/api/inquiries")
async def create_inquiry(body: InquiryCreate):
    if not db.pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    pw_hash = _hash_password(body.password)
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO inquiries (author_name, password_hash, title, content) VALUES ($1, $2, $3, $4) RETURNING id, created_at",
            body.author_name, pw_hash, body.title, body.content,
        )
    return {"id": row["id"], "created_at": row["created_at"].isoformat()}


@router.post("/api/inquiries/{inquiry_id}/verify")
async def verify_inquiry(inquiry_id: int, body: InquiryVerify):
    if not db.pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, author_name, password_hash, title, content, status, created_at FROM inquiries WHERE id = $1",
            inquiry_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="문의를 찾을 수 없습니다")

        if row["author_name"] != body.author_name:
            raise HTTPException(status_code=403, detail="작성자 이름 또는 비밀번호가 올바르지 않습니다")

        if not _verify_password(body.password, row["password_hash"]):
            raise HTTPException(status_code=403, detail="작성자 이름 또는 비밀번호가 올바르지 않습니다")

        replies = await conn.fetch(
            "SELECT id, content, created_at FROM inquiry_replies WHERE inquiry_id = $1 ORDER BY created_at",
            inquiry_id,
        )

    return {
        "id": row["id"],
        "author_name": row["author_name"],
        "title": row["title"],
        "content": row["content"],
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "replies": [
            {
                "id": rp["id"],
                "content": rp["content"],
                "created_at": rp["created_at"].isoformat() if rp["created_at"] else None,
            }
            for rp in replies
        ],
    }


# --- 관리자 엔드포인트 ---

@router.get("/admin/inquiries")
async def admin_list_inquiries(_=Depends(verify_token)):
    if not db.pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, author_name, title, content, status, created_at FROM inquiries ORDER BY id DESC"
        )
    return [
        {
            "id": r["id"],
            "author_name": r["author_name"],
            "title": r["title"],
            "content": r["content"],
            "status": r["status"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


@router.get("/admin/inquiries/{inquiry_id}")
async def admin_get_inquiry(inquiry_id: int, _=Depends(verify_token)):
    if not db.pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, author_name, title, content, status, created_at FROM inquiries WHERE id = $1",
            inquiry_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="문의를 찾을 수 없습니다")
        replies = await conn.fetch(
            "SELECT id, content, created_at FROM inquiry_replies WHERE inquiry_id = $1 ORDER BY created_at",
            inquiry_id,
        )
    return {
        "id": row["id"],
        "author_name": row["author_name"],
        "title": row["title"],
        "content": row["content"],
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "replies": [
            {
                "id": rp["id"],
                "content": rp["content"],
                "created_at": rp["created_at"].isoformat() if rp["created_at"] else None,
            }
            for rp in replies
        ],
    }


@router.post("/admin/inquiries/{inquiry_id}/reply")
async def admin_reply_inquiry(inquiry_id: int, body: ReplyCreate, _=Depends(verify_token)):
    if not db.pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.pool.acquire() as conn:
        exists = await conn.fetchval("SELECT 1 FROM inquiries WHERE id = $1", inquiry_id)
        if not exists:
            raise HTTPException(status_code=404, detail="문의를 찾을 수 없습니다")
        await conn.execute(
            "INSERT INTO inquiry_replies (inquiry_id, content) VALUES ($1, $2)",
            inquiry_id, body.content,
        )
        await conn.execute(
            "UPDATE inquiries SET status = 'answered' WHERE id = $1",
            inquiry_id,
        )
    return {"message": "답변 등록 완료"}


@router.delete("/admin/inquiries/{inquiry_id}")
async def admin_delete_inquiry(inquiry_id: int, _=Depends(verify_token)):
    if not db.pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.pool.acquire() as conn:
        result = await conn.execute("DELETE FROM inquiries WHERE id = $1", inquiry_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="문의를 찾을 수 없습니다")
    return {"message": "삭제 완료"}
