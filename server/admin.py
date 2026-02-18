"""관리자 API 라우터 — 문서 업로드, OCR, RAG 파이프라인 관리"""

import os
import secrets
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Header
from pydantic import BaseModel

import db
from ocr import extract_text
from rag import chunk_text, store_chunks, get_embeddings

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
async def list_documents(purpose: str = None, _=Depends(verify_token)):
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        if purpose:
            rows = await conn.fetch(
                "SELECT id, filename, file_type, status, error_msg, purpose, category, created_at FROM documents WHERE purpose = $1 ORDER BY id DESC",
                purpose,
            )
        else:
            rows = await conn.fetch(
                "SELECT id, filename, file_type, status, error_msg, purpose, category, created_at FROM documents ORDER BY id DESC"
            )
    return [
        {
            "id": row["id"],
            "filename": row["filename"],
            "file_type": row["file_type"],
            "status": row["status"],
            "error_msg": row["error_msg"],
            "purpose": row["purpose"],
            "category": row.get("category", "미분류"),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]


# --- 문서 상세 ---

@router.get("/documents/{doc_id}")
async def get_document(doc_id: int, _=Depends(verify_token)):
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
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
async def upload_document(
    file: UploadFile = File(...),
    purpose: str = Form("consultant"),
    _=Depends(verify_token),
):
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    if purpose not in ("consultant", "rag_session"):
        raise HTTPException(status_code=400, detail="purpose는 'consultant' 또는 'rag_session'이어야 합니다")

    # 파일 확장자 검증
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 파일 형식: {ext}")

    file_type = _get_file_type(file.filename)

    # DB에 문서 레코드 생성 (processing)
    async with db.vector_pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO documents (filename, file_type, status, purpose) VALUES ($1, $2, 'processing', $3) RETURNING id",
            file.filename,
            file_type,
            purpose,
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
        async with db.vector_pool.acquire() as conn:
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


# --- 청크 텍스트 수정 ---

@router.patch("/documents/{doc_id}/chunks/{chunk_id}")
async def update_chunk(doc_id: int, chunk_id: int, body: dict, _=Depends(verify_token)):
    new_text = body.get("chunk_text", "").strip()
    if not new_text:
        raise HTTPException(status_code=400, detail="chunk_text가 비어있습니다")
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM document_chunks WHERE id = $1 AND document_id = $2",
            chunk_id, doc_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="해당 청크를 찾을 수 없습니다")
        embedding = get_embeddings([new_text])[0]
        await conn.execute(
            "UPDATE document_chunks SET chunk_text = $1, embedding = $2::vector WHERE id = $3 AND document_id = $4",
            new_text, str(embedding), chunk_id, doc_id,
        )
    return {"message": "청크 수정 완료"}


# --- 문서 삭제 ---

@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: int, _=Depends(verify_token)):
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM documents WHERE id = $1", doc_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")
    return {"message": "삭제 완료"}


# --- 문서 카테고리 업데이트 ---

class CategoryUpdate(BaseModel):
    category: str


@router.patch("/documents/{doc_id}/category")
async def update_document_category(doc_id: int, body: CategoryUpdate, _=Depends(verify_token)):
    """문서 카테고리 업데이트"""
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    category = body.category.strip()
    if not category:
        raise HTTPException(status_code=400, detail="카테고리를 입력하세요")

    async with db.vector_pool.acquire() as conn:
        # 문서 존재 여부 확인
        doc = await conn.fetchrow("SELECT id FROM documents WHERE id = $1", doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")

        # 카테고리 업데이트
        await conn.execute(
            "UPDATE documents SET category = $1 WHERE id = $2",
            category,
            doc_id,
        )

    return {"message": "카테고리가 업데이트되었습니다", "category": category}


# --- 유틸 ---

async def _update_doc_status(doc_id: int, status: str, error_msg: str | None):
    if not db.vector_pool:
        return
    async with db.vector_pool.acquire() as conn:
        await conn.execute(
            "UPDATE documents SET status = $1, error_msg = $2 WHERE id = $3",
            status,
            error_msg,
            doc_id,
        )


# ============================================================
#  사이트 설정 관리 (로고, 히어로, 회사 정보 등)
# ============================================================

@router.get("/settings")
async def get_settings(_=Depends(verify_token)):
    """전체 사이트 설정 조회 (관리자용)"""
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        rows = await conn.fetch("SELECT key, value, updated_at FROM site_settings")
    return {
        row["key"]: {
            "value": row["value"],
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }
        for row in rows
    }


@router.put("/settings/{key}")
async def update_setting(key: str, body: dict, _=Depends(verify_token)):
    """개별 설정 업데이트"""
    value = body.get("value", "")
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO site_settings (key, value, updated_at)
               VALUES ($1, $2, NOW())
               ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()""",
            key, value,
        )
    return {"message": "설정 저장 완료", "key": key}


@router.post("/settings/logo")
async def upload_logo(body: dict, _=Depends(verify_token)):
    """로고 업로드 (base64 data URI)"""
    logo_data = body.get("logo", "")
    if not logo_data:
        raise HTTPException(status_code=400, detail="로고 데이터가 필요합니다")

    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    async with db.vector_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO site_settings (key, value, updated_at)
               VALUES ('logo', $1, NOW())
               ON CONFLICT (key) DO UPDATE SET value = $1, updated_at = NOW()""",
            logo_data,
        )
    return {"message": "로고 저장 완료"}


# ============================================================
#  대시보드 통계
# ============================================================

@router.get("/stats")
async def get_dashboard_stats(_=Depends(verify_token)):
    """대시보드 통계 조회"""
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    async with db.vector_pool.acquire() as conn:
        # 문서 통계
        total_docs = await conn.fetchval("SELECT COUNT(*) FROM documents")
        docs_by_purpose = await conn.fetch(
            "SELECT purpose, COUNT(*) as count FROM documents GROUP BY purpose"
        )

        # 메일 통계
        total_mails = await conn.fetchval("SELECT COUNT(*) FROM mail_compositions")
        mails_today = await conn.fetchval(
            "SELECT COUNT(*) FROM mail_compositions WHERE created_at::date = CURRENT_DATE"
        )
        mails_this_week = await conn.fetchval(
            "SELECT COUNT(*) FROM mail_compositions WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'"
        )
        mails_this_month = await conn.fetchval(
            "SELECT COUNT(*) FROM mail_compositions WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'"
        )

        # RAG 대화 통계
        total_conversations = await conn.fetchval("SELECT COUNT(*) FROM conversations")
        conversations_today = await conn.fetchval(
            "SELECT COUNT(*) FROM conversations WHERE created_at::date = CURRENT_DATE"
        )

        # 프롬프트 예시 & 서명 개수
        prompt_examples_count = await conn.fetchval("SELECT COUNT(*) FROM mail_prompt_examples")
        signatures_count = await conn.fetchval("SELECT COUNT(*) FROM mail_signatures")

    # 견적문의 통계 (일반 DB)
    total_inquiries = 0
    inquiries_today = 0
    if db.pool:
        async with db.pool.acquire() as conn:
            total_inquiries = await conn.fetchval("SELECT COUNT(*) FROM inquiries")
            inquiries_today = await conn.fetchval(
                "SELECT COUNT(*) FROM inquiries WHERE created_at::date = CURRENT_DATE"
            )

    return {
        "documents": {
            "total": total_docs,
            "by_purpose": {row["purpose"]: row["count"] for row in docs_by_purpose},
        },
        "mails": {
            "total": total_mails,
            "today": mails_today,
            "this_week": mails_this_week,
            "this_month": mails_this_month,
        },
        "conversations": {
            "total": total_conversations,
            "today": conversations_today,
        },
        "inquiries": {
            "total": total_inquiries,
            "today": inquiries_today,
        },
        "settings": {
            "prompt_examples": prompt_examples_count,
            "signatures": signatures_count,
        },
    }


@router.get("/logs/mail")
async def get_mail_logs(limit: int = 50, _=Depends(verify_token)):
    """메일 작성 로그 조회"""
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    async with db.vector_pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, incoming_email, korean_draft, translated_draft,
                      detected_lang, tone, created_at
               FROM mail_compositions
               ORDER BY created_at DESC
               LIMIT $1""",
            limit
        )

    return [
        {
            "id": row["id"],
            "incoming_preview": row["incoming_email"][:100] + "..." if len(row["incoming_email"]) > 100 else row["incoming_email"],
            "draft_preview": row["korean_draft"][:100] + "..." if len(row["korean_draft"]) > 100 else row["korean_draft"],
            "detected_lang": row["detected_lang"],
            "tone": row["tone"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]


# ============================================================
#  카테고리 관리
# ============================================================

@router.get("/categories")
async def get_categories(_=Depends(verify_token)):
    """카테고리 목록 조회"""
    if not db.pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM categories ORDER BY id")

    return [dict(row) for row in rows]


@router.post("/categories")
async def create_category(body: dict, _=Depends(verify_token)):
    """카테고리 생성"""
    if not db.pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    code = body.get("code", "").strip()
    name_ko = body.get("name_ko", "").strip()
    name_en = body.get("name_en", "").strip()

    if not code or not name_ko:
        raise HTTPException(status_code=400, detail="코드와 한글명은 필수입니다")

    async with db.pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                "INSERT INTO categories (code, name_ko, name_en) VALUES ($1, $2, $3) RETURNING id",
                code, name_ko, name_en
            )
            return {"id": row["id"], "message": "카테고리 생성 완료"}
        except Exception as e:
            if "unique" in str(e).lower():
                raise HTTPException(status_code=400, detail="이미 존재하는 카테고리 코드입니다")
            raise HTTPException(status_code=500, detail=str(e))


@router.delete("/categories/{category_id}")
async def delete_category(category_id: int, _=Depends(verify_token)):
    """카테고리 삭제"""
    if not db.pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    async with db.pool.acquire() as conn:
        result = await conn.execute("DELETE FROM categories WHERE id = $1", category_id)

    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다")

    return {"message": "삭제 완료"}


# ============================================================
#  이미지 업로드
# ============================================================

@router.post("/upload-image")
async def upload_image(body: dict, _=Depends(verify_token)):
    """이미지 업로드 (Base64)"""
    image_data = body.get("image", "")

    if not image_data:
        raise HTTPException(status_code=400, detail="이미지 데이터가 필요합니다")

    # Base64 data URI 형식 확인
    if not image_data.startswith("data:image/"):
        raise HTTPException(status_code=400, detail="올바른 이미지 형식이 아닙니다")

    # 이미지를 그대로 반환 (data URI)
    return {"url": image_data}


# ============================================================
#  상품 관리
# ============================================================

@router.get("/products")
async def get_products(category: str = None, search: str = None, _=Depends(verify_token)):
    """상품 목록 조회"""
    if not db.pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    products = await db.get_all_products(category, search)
    return products


@router.get("/products/{product_id}")
async def get_product(product_id: int, _=Depends(verify_token)):
    """상품 상세 조회"""
    if not db.pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    async with db.pool.acquire() as conn:
        product = await conn.fetchrow("SELECT * FROM products WHERE id = $1", product_id)
        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")

    return dict(product)


@router.post("/products")
async def create_product(body: dict, _=Depends(verify_token)):
    """상품 생성"""
    import json
    if not db.pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO products (image, part_no, price, brand, category, name, description,
                                      category_name, detail_info, specs, compatibility)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8::jsonb, $9::jsonb, $10::jsonb, $11::jsonb)
               RETURNING id""",
            body.get("image", ""),
            body.get("part_no", ""),
            body.get("price", ""),
            body.get("brand", ""),
            body.get("category", ""),
            json.dumps(body.get("name", {})),
            json.dumps(body.get("description", {})),
            json.dumps(body.get("category_name", {})),
            json.dumps(body.get("detail_info", {})),
            json.dumps(body.get("specs", {})),
            json.dumps(body.get("compatibility", {}))
        )

    return {"id": row["id"], "message": "상품 생성 완료"}


@router.put("/products/{product_id}")
async def update_product(product_id: int, body: dict, _=Depends(verify_token)):
    """상품 수정"""
    import json
    if not db.pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    async with db.pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE products
               SET image = $1, part_no = $2, price = $3, brand = $4, category = $5,
                   name = $6::jsonb, description = $7::jsonb, category_name = $8::jsonb, detail_info = $9::jsonb,
                   specs = $10::jsonb, compatibility = $11::jsonb, updated_at = NOW()
               WHERE id = $12""",
            body.get("image", ""),
            body.get("part_no", ""),
            body.get("price", ""),
            body.get("brand", ""),
            body.get("category", ""),
            json.dumps(body.get("name", {})),
            json.dumps(body.get("description", {})),
            json.dumps(body.get("category_name", {})),
            json.dumps(body.get("detail_info", {})),
            json.dumps(body.get("specs", {})),
            json.dumps(body.get("compatibility", {})),
            product_id
        )

    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")

    return {"message": "상품 수정 완료"}


@router.delete("/products/{product_id}")
async def delete_product(product_id: int, _=Depends(verify_token)):
    """상품 삭제"""
    if not db.pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    async with db.pool.acquire() as conn:
        result = await conn.execute("DELETE FROM products WHERE id = $1", product_id)

    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")

    return {"message": "상품 삭제 완료"}


# ===== 번역 API =====

@router.post("/translate")
async def translate_product(body: dict, _=Depends(verify_token)):
    """
    상품 정보 자동 번역 (Gemini + Web Search)

    Request body:
    {
        "text": "번역할 텍스트",
        "target_lang": "en" or "cn",
        "context": {
            "part_no": "부품번호",
            "brand": "브랜드",
            "category": "카테고리"
        }
    }
    """
    import google.genai as genai

    text = body.get("text", "")
    target_lang = body.get("target_lang", "en")
    context = body.get("context", {})

    if not text:
        raise HTTPException(status_code=400, detail="번역할 텍스트가 필요합니다")

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="API 키가 설정되지 않았습니다")

    try:
        client = genai.Client(api_key=api_key)

        lang_names = {
            "en": "English",
            "cn": "Chinese (Simplified)"
        }

        target_lang_name = lang_names.get(target_lang, "English")

        # 웹 검색 포함 프롬프트
        prompt = f"""You are a professional translator specializing in marine engine parts.

Translate the following Korean text to {target_lang_name}:

Korean text: {text}

Context:
- Part Number: {context.get('part_no', 'N/A')}
- Brand: {context.get('brand', 'N/A')}
- Category: {context.get('category', 'N/A')}

Requirements:
1. Use accurate technical terminology for marine engine parts
2. Search the web if needed to find the correct translation for part names
3. Keep brand names and part numbers unchanged
4. Maintain professional tone
5. Return ONLY the translated text, no explanations

Translated text:"""

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=1000
            )
        )

        translated_text = response.text.strip()

        return {"translated": translated_text}

    except Exception as e:
        print(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail=f"번역 실패: {str(e)}")
