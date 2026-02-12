"""RAG 세션 전용 채팅 API 라우터"""

import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

import db
from rag import search_similar_chunks
from admin import verify_token

router = APIRouter(prefix="/admin/rag", tags=["rag-chat"])

CONVERSATION_TTL_DAYS = 7  # 대화 보관 기간 (일)


# --- 요청/응답 모델 ---

class RagChatRequest(BaseModel):
    conversation_id: int
    message: str
    document_ids: list[int] | None = None


class ConversationCreate(BaseModel):
    title: str = "새 대화"


class ConversationRename(BaseModel):
    title: str


# --- 7일 초과 대화 자동 삭제 (saved 제외) ---

async def cleanup_old_conversations():
    """7일 이상 된 대화를 자동 삭제한다 (saved=TRUE는 제외). 서버 시작 시 호출."""
    if not db.vector_pool:
        return
    try:
        async with db.vector_pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM rag_conversations WHERE saved = FALSE AND updated_at < NOW() - INTERVAL '{CONVERSATION_TTL_DAYS} days'"
            )
            count = int(result.split()[-1]) if result else 0
            if count > 0:
                print(f"[RAG 정리] {count}개의 오래된 대화 삭제 완료", flush=True)
    except Exception as e:
        print(f"[RAG 정리] 오류: {e}", flush=True)


# --- 대화 목록 ---

@router.get("/conversations")
async def list_conversations(_=Depends(verify_token)):
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, title, saved, created_at, updated_at FROM rag_conversations ORDER BY updated_at DESC"
        )
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "saved": row["saved"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }
        for row in rows
    ]


# --- 새 대화 생성 ---

@router.post("/conversations")
async def create_conversation(body: ConversationCreate = None, _=Depends(verify_token)):
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    title = body.title if body else "새 대화"
    async with db.vector_pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO rag_conversations (title) VALUES ($1) RETURNING id, title, saved, created_at, updated_at",
            title,
        )
    return {
        "id": row["id"],
        "title": row["title"],
        "saved": row["saved"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


# --- 대화 + 메시지 조회 ---

@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: int, _=Depends(verify_token)):
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        conv = await conn.fetchrow(
            "SELECT id, title, saved, created_at, updated_at FROM rag_conversations WHERE id = $1",
            conv_id,
        )
        if not conv:
            raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")
        messages = await conn.fetch(
            "SELECT id, role, content, refs, created_at FROM rag_messages WHERE conversation_id = $1 ORDER BY id",
            conv_id,
        )

    parsed_messages = []
    for m in messages:
        refs_raw = m["refs"]
        if isinstance(refs_raw, list):
            refs = refs_raw
        elif isinstance(refs_raw, str):
            refs = json.loads(refs_raw) if refs_raw else []
        else:
            refs = []
        parsed_messages.append({
            "id": m["id"],
            "role": m["role"],
            "content": m["content"],
            "references": refs,
            "created_at": m["created_at"].isoformat() if m["created_at"] else None,
        })

    return {
        "id": conv["id"],
        "title": conv["title"],
        "saved": conv["saved"],
        "created_at": conv["created_at"].isoformat() if conv["created_at"] else None,
        "updated_at": conv["updated_at"].isoformat() if conv["updated_at"] else None,
        "messages": parsed_messages,
    }


# --- 대화 삭제 ---

@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: int, _=Depends(verify_token)):
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM rag_conversations WHERE id = $1", conv_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")
    return {"message": "삭제 완료"}


# --- 대화 이름 변경 ---

@router.patch("/conversations/{conv_id}")
async def rename_conversation(conv_id: int, body: ConversationRename, _=Depends(verify_token)):
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="제목을 입력하세요")
    async with db.vector_pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE rag_conversations SET title = $1 WHERE id = $2",
            title,
            conv_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")
    return {"message": "변경 완료", "title": title}


# --- 대화 저장/해제 토글 ---

@router.post("/conversations/{conv_id}/save")
async def toggle_save_conversation(conv_id: int, _=Depends(verify_token)):
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE rag_conversations SET saved = NOT COALESCE(saved, FALSE) WHERE id = $1 RETURNING saved",
            conv_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")
    return {"saved": row["saved"]}


# --- RAG 세션용 문서 목록 ---

@router.get("/documents")
async def list_rag_documents(_=Depends(verify_token)):
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, filename, file_type, status FROM documents WHERE purpose = 'rag_session' AND status = 'done' ORDER BY id DESC"
        )
    return [
        {
            "id": row["id"],
            "filename": row["filename"],
            "file_type": row["file_type"],
            "status": row["status"],
        }
        for row in rows
    ]


# --- RAG 채팅 (메시지 전송 + AI 답변) ---

@router.post("/chat")
async def rag_chat(req: RagChatRequest, _=Depends(verify_token)):
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    # 대화 존재 확인
    async with db.vector_pool.acquire() as conn:
        conv = await conn.fetchrow(
            "SELECT id FROM rag_conversations WHERE id = $1", req.conversation_id
        )
        if not conv:
            raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")

    # 유사 청크 검색 (rag_session 문서만, 선택된 문서만)
    chunks = await search_similar_chunks(
        query=req.message,
        top_k=5,
        purpose="rag_session",
        document_ids=req.document_ids,
    )

    # 참조 정보 구성 (similarity > 0.3)
    references = [
        {
            "filename": c["filename"],
            "chunk_text": c["chunk_text"],
            "similarity": round(c["similarity"], 4),
        }
        for c in chunks
        if c["similarity"] > 0.3
    ]

    # 이전 대화 이력 가져오기 (최근 10개)
    async with db.vector_pool.acquire() as conn:
        prev_rows = await conn.fetch(
            "SELECT role, content FROM rag_messages WHERE conversation_id = $1 ORDER BY id DESC LIMIT 10",
            req.conversation_id,
        )
    prev_messages = [{"role": r["role"], "content": r["content"]} for r in reversed(prev_rows)]

    # AI 답변 생성
    reply = _generate_rag_answer(req.message, references, prev_messages)

    # 사용자 메시지 + AI 답변 DB 저장
    refs_json = json.dumps(references, ensure_ascii=False)
    async with db.vector_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO rag_messages (conversation_id, role, content) VALUES ($1, 'user', $2)",
            req.conversation_id,
            req.message,
        )
        await conn.execute(
            "INSERT INTO rag_messages (conversation_id, role, content, refs) VALUES ($1, 'assistant', $2, $3::jsonb)",
            req.conversation_id,
            reply,
            refs_json,
        )
        # 대화 updated_at 갱신 + 첫 메시지면 제목 자동 설정
        title_update = req.message[:30] + ("..." if len(req.message) > 30 else "")
        await conn.execute(
            """
            UPDATE rag_conversations
            SET updated_at = NOW(),
                title = CASE WHEN title = '새 대화' THEN $2 ELSE title END
            WHERE id = $1
            """,
            req.conversation_id,
            title_update,
        )

    return {
        "reply": reply,
        "references": references,
        "conversation_id": req.conversation_id,
    }


def _generate_rag_answer(
    user_message: str,
    references: list[dict],
    prev_messages: list[dict],
) -> str:
    """Gemini로 RAG 기반 답변을 생성한다 (동기 함수)."""
    from decouple import config
    import google.genai as genai
    from google.genai import types

    api_key = config("GOOGLE_API_KEY", default="")
    if not api_key:
        return "API Key가 설정되지 않았습니다."

    # 참조 문서 컨텍스트 구성
    context_lines = []
    for ref in references:
        context_lines.append(f"[{ref['filename']}] {ref['chunk_text']}")
    context = "\n---\n".join(context_lines) if context_lines else "(관련 문서 내용 없음)"

    system_prompt = f"""당신은 기술 문서 Q&A 어시스턴트입니다.
아래 참조 문서를 바탕으로 사용자의 질문에 정확하게 답변하세요.
문서에 없는 내용은 추측하지 말고 "해당 내용은 문서에서 찾을 수 없습니다"라고 답하세요.
답변은 한국어로 작성하세요.

## 참조 문서
{context}
"""

    client = genai.Client(api_key=api_key)

    contents = []
    for m in prev_messages:
        role = "model" if m["role"] == "assistant" else m["role"]
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.3,
            ),
        )
        return response.text
    except Exception as e:
        print(f"RAG 채팅 AI 오류: {e}", flush=True)
        return "AI 답변 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
