"""메일 작성 자동화 API 라우터 + Gmail 연동"""

import json
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

import db
from rag import search_similar_chunks
from admin import verify_token
import gmail_service

router = APIRouter(prefix="/admin/mail", tags=["mail-compose"])


# --- 요청/응답 모델 ---

class ComposeRequest(BaseModel):
    incoming_email: str
    document_ids: list[int] | None = None
    tone: str = "formal"  # formal, friendly, concise


class TranslateRequest(BaseModel):
    korean_text: str
    target_lang: str = "en"


class SaveRequest(BaseModel):
    incoming_email: str
    detected_lang: str = "en"
    tone: str = "formal"
    korean_draft: str
    translated_draft: str = ""
    document_ids: list[int] | None = None
    refs: list[dict] | None = None


# --- 메일 작성 (견적 분석 + 한국어 초안 생성) ---

@router.post("/compose")
async def compose_mail(req: ComposeRequest, _=Depends(verify_token)):
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    # 1. 수신 메일에서 유사 청크 검색 (견적서 관련 문서)
    chunks = await search_similar_chunks(
        query=req.incoming_email,
        top_k=8,
        purpose="rag_session",
        document_ids=req.document_ids,
    )

    references = [
        {
            "filename": c["filename"],
            "chunk_text": c["chunk_text"],
            "similarity": round(c["similarity"], 4),
        }
        for c in chunks
        if c["similarity"] > 0.25
    ]

    # 2. AI로 분석 + 한국어 초안 생성
    result = _generate_mail_draft(req.incoming_email, references, req.tone)

    return {
        "detected_lang": result["detected_lang"],
        "korean_draft": result["korean_draft"],
        "analysis": result["analysis"],
        "references": references,
    }


# --- 번역 ---

@router.post("/translate")
async def translate_mail(req: TranslateRequest, _=Depends(verify_token)):
    translated = _translate_text(req.korean_text, req.target_lang)
    return {"translated": translated, "target_lang": req.target_lang}


# --- 이력 저장 ---

@router.post("/save")
async def save_composition(req: SaveRequest, _=Depends(verify_token)):
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO mail_compositions
               (incoming_email, detected_lang, tone, korean_draft, translated_draft, document_ids, refs)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb)
               RETURNING id, created_at""",
            req.incoming_email,
            req.detected_lang,
            req.tone,
            req.korean_draft,
            req.translated_draft,
            json.dumps(req.document_ids or [], ensure_ascii=False),
            json.dumps(req.refs or [], ensure_ascii=False),
        )
    return {
        "id": row["id"],
        "created_at": row["created_at"].isoformat(),
        "message": "저장 완료",
    }


# --- 이력 목록 ---

@router.get("/history")
async def list_history(_=Depends(verify_token)):
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, incoming_email, detected_lang, tone, created_at
               FROM mail_compositions ORDER BY id DESC LIMIT 50"""
        )
    return [
        {
            "id": row["id"],
            "incoming_email": row["incoming_email"][:100] + ("..." if len(row["incoming_email"]) > 100 else ""),
            "detected_lang": row["detected_lang"],
            "tone": row["tone"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]


# --- 이력 상세 ---

@router.get("/history/{comp_id}")
async def get_history_item(comp_id: int, _=Depends(verify_token)):
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM mail_compositions WHERE id = $1", comp_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="이력을 찾을 수 없습니다")

    refs_raw = row["refs"]
    if isinstance(refs_raw, list):
        refs = refs_raw
    elif isinstance(refs_raw, str):
        refs = json.loads(refs_raw) if refs_raw else []
    else:
        refs = []

    doc_ids_raw = row["document_ids"]
    if isinstance(doc_ids_raw, list):
        doc_ids = doc_ids_raw
    elif isinstance(doc_ids_raw, str):
        doc_ids = json.loads(doc_ids_raw) if doc_ids_raw else []
    else:
        doc_ids = []

    return {
        "id": row["id"],
        "incoming_email": row["incoming_email"],
        "detected_lang": row["detected_lang"],
        "tone": row["tone"],
        "korean_draft": row["korean_draft"],
        "translated_draft": row["translated_draft"],
        "document_ids": doc_ids,
        "refs": refs,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


# --- 이력 삭제 ---

@router.delete("/history/{comp_id}")
async def delete_history_item(comp_id: int, _=Depends(verify_token)):
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM mail_compositions WHERE id = $1", comp_id
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="이력을 찾을 수 없습니다")
    return {"message": "삭제 완료"}


# --- AI 함수들 ---

def _generate_mail_draft(
    incoming_email: str,
    references: list[dict],
    tone: str,
) -> dict:
    """수신 메일을 분석하고 한국어 답장 초안을 생성한다."""
    from decouple import config
    import google.genai as genai
    from google.genai import types

    api_key = config("GOOGLE_API_KEY", default="")
    if not api_key:
        return {
            "detected_lang": "unknown",
            "korean_draft": "API Key가 설정되지 않았습니다.",
            "analysis": "",
        }

    # 참조 문서 컨텍스트
    context_lines = []
    for ref in references:
        context_lines.append(f"[{ref['filename']}] {ref['chunk_text']}")
    context = "\n---\n".join(context_lines) if context_lines else "(관련 문서 없음)"

    tone_desc = {
        "formal": "격식체, 비즈니스 정중한 톤",
        "friendly": "친근하면서도 프로페셔널한 톤",
        "concise": "간결하고 핵심만 담은 톤",
    }.get(tone, "격식체, 비즈니스 정중한 톤")

    system_prompt = f"""당신은 영마린테크(선박 엔진 부품 B2B 회사)의 전문 메일 작성 어시스턴트입니다.

## 작업
1. 수신된 견적/문의 메일을 분석합니다
2. 메일의 언어를 감지합니다 (영어=en, 일본어=ja, 중국어=zh, 한국어=ko 등)
3. 요청 사항(부품명, 수량, 납기 등)을 파악합니다
4. 아래 참조 문서를 활용하여 정확한 정보를 포함한 한국어 답장 초안을 작성합니다

## 참조 문서 (견적서/기술 자료)
{context}

## 톤
{tone_desc}

## 응답 형식 (반드시 JSON)
{{
    "detected_lang": "en",
    "analysis": "메일 분석 요약 (한국어, 2-3줄: 발신자, 요청 부품, 수량, 특이사항 등)",
    "korean_draft": "한국어 답장 초안 (메일 본문만, 인사~맺음까지 완전한 메일)"
}}

## 주의사항
- 한국어 초안은 실제 발송할 메일 수준으로 완성도 있게 작성
- 참조 문서에 가격/사양 정보가 있으면 반드시 포함
- 문서에 없는 정보는 "[확인 필요]"로 표시
- 답장 초안에는 영마린테크 담당자 서명 포함
"""

    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[{"role": "user", "parts": [{"text": incoming_email}]}],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.4,
                response_mime_type="application/json",
            ),
        )
        result = json.loads(response.text)
        return {
            "detected_lang": result.get("detected_lang", "en"),
            "korean_draft": result.get("korean_draft", ""),
            "analysis": result.get("analysis", ""),
        }
    except Exception as e:
        print(f"메일 초안 생성 오류: {e}", flush=True)
        return {
            "detected_lang": "unknown",
            "korean_draft": "AI 답변 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            "analysis": str(e),
        }


# ============================================================
#  Gmail 연동 엔드포인트
# ============================================================

class GmailConnectRequest(BaseModel):
    email: str
    app_password: str


class GmailSettingsRequest(BaseModel):
    check_time: str = "09:00"
    auto_reply_enabled: bool = False


@router.post("/gmail/connect")
async def gmail_connect(req: GmailConnectRequest, _=Depends(verify_token)):
    """Gmail 연결 (IMAP 테스트 + 설정 저장)"""
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    # IMAP 연결 테스트
    try:
        await asyncio.to_thread(gmail_service.test_connection, req.email, req.app_password)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gmail 연결 실패: {e}")

    # 기존 설정 삭제 후 새로 저장
    async with db.vector_pool.acquire() as conn:
        await conn.execute("DELETE FROM gmail_config")
        await conn.fetchrow(
            """INSERT INTO gmail_config (email, app_password)
               VALUES ($1, $2) RETURNING id""",
            req.email, req.app_password,
        )
    return {"message": "Gmail 연결 성공", "email": req.email}


@router.post("/gmail/disconnect")
async def gmail_disconnect(_=Depends(verify_token)):
    """Gmail 연결 해제"""
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        await conn.execute("DELETE FROM gmail_config")
    return {"message": "Gmail 연결 해제 완료"}


@router.get("/gmail/status")
async def gmail_status(_=Depends(verify_token)):
    """Gmail 연결 상태 조회"""
    if not db.vector_pool:
        return {"connected": False}
    async with db.vector_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM gmail_config LIMIT 1")
    if not row:
        return {"connected": False}
    return {
        "connected": True,
        "email": row["email"],
        "check_time": row["check_time"],
        "auto_reply_enabled": row["auto_reply_enabled"],
        "last_checked_at": row["last_checked_at"].isoformat() if row["last_checked_at"] else None,
    }


@router.post("/gmail/settings")
async def gmail_settings(req: GmailSettingsRequest, _=Depends(verify_token)):
    """자동 체크 설정 변경"""
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE gmail_config SET check_time = $1, auto_reply_enabled = $2",
            req.check_time, req.auto_reply_enabled,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Gmail 설정이 없습니다. 먼저 연결하세요.")
    return {"message": "설정 저장 완료", "check_time": req.check_time, "auto_reply_enabled": req.auto_reply_enabled}


@router.post("/gmail/fetch")
async def gmail_fetch(_=Depends(verify_token)):
    """수동으로 메일 가져오기"""
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    async with db.vector_pool.acquire() as conn:
        config = await conn.fetchrow("SELECT * FROM gmail_config LIMIT 1")
    if not config:
        raise HTTPException(status_code=400, detail="Gmail 설정이 없습니다")

    since = config["last_checked_at"]
    emails = await asyncio.to_thread(
        gmail_service.fetch_new_emails, config["email"], config["app_password"], since
    )

    saved_count = 0
    async with db.vector_pool.acquire() as conn:
        for em in emails:
            # 중복 체크 (gmail_uid)
            exists = await conn.fetchval(
                "SELECT 1 FROM inbox_emails WHERE gmail_uid = $1", em["uid"]
            )
            if exists:
                continue
            await conn.execute(
                """INSERT INTO inbox_emails (gmail_uid, from_addr, from_name, subject, body, received_at)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                em["uid"], em["from_addr"], em["from_name"],
                em["subject"], em["body"], em["received_at"],
            )
            saved_count += 1
        # last_checked_at 갱신
        await conn.execute(
            "UPDATE gmail_config SET last_checked_at = $1",
            datetime.now(timezone.utc),
        )

    return {"message": f"{saved_count}건의 새 메일을 가져왔습니다", "total_fetched": len(emails), "new_saved": saved_count}


@router.get("/gmail/inbox")
async def gmail_inbox(_=Depends(verify_token)):
    """수신함 목록"""
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, gmail_uid, from_addr, from_name, subject, body, received_at, status, composition_id, created_at
               FROM inbox_emails ORDER BY received_at DESC NULLS LAST LIMIT 100"""
        )
    return [
        {
            "id": r["id"],
            "from_addr": r["from_addr"],
            "from_name": r["from_name"],
            "subject": r["subject"],
            "body": r["body"][:200] + ("..." if r["body"] and len(r["body"]) > 200 else "") if r["body"] else "",
            "received_at": r["received_at"].isoformat() if r["received_at"] else None,
            "status": r["status"],
            "composition_id": r["composition_id"],
        }
        for r in rows
    ]


@router.get("/gmail/inbox/{inbox_id}")
async def gmail_inbox_detail(inbox_id: int, _=Depends(verify_token)):
    """수신 메일 상세"""
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM inbox_emails WHERE id = $1", inbox_id)
    if not row:
        raise HTTPException(status_code=404, detail="메일을 찾을 수 없습니다")

    result = {
        "id": row["id"],
        "from_addr": row["from_addr"],
        "from_name": row["from_name"],
        "subject": row["subject"],
        "body": row["body"],
        "received_at": row["received_at"].isoformat() if row["received_at"] else None,
        "status": row["status"],
        "composition_id": row["composition_id"],
    }

    # 연결된 초안이 있으면 포함
    if row["composition_id"]:
        comp = await conn.fetchrow(
            "SELECT korean_draft, translated_draft, detected_lang, tone FROM mail_compositions WHERE id = $1",
            row["composition_id"],
        )
        if comp:
            result["draft"] = {
                "korean_draft": comp["korean_draft"],
                "translated_draft": comp["translated_draft"],
                "detected_lang": comp["detected_lang"],
                "tone": comp["tone"],
            }
    return result


@router.post("/gmail/send/{inbox_id}")
async def gmail_send(inbox_id: int, _=Depends(verify_token)):
    """답장 발송 (번역본을 원래 발신자에게 SMTP 전송)"""
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")

    async with db.vector_pool.acquire() as conn:
        config = await conn.fetchrow("SELECT * FROM gmail_config LIMIT 1")
        if not config:
            raise HTTPException(status_code=400, detail="Gmail 설정이 없습니다")

        inbox = await conn.fetchrow("SELECT * FROM inbox_emails WHERE id = $1", inbox_id)
        if not inbox:
            raise HTTPException(status_code=404, detail="수신 메일을 찾을 수 없습니다")

        if not inbox["composition_id"]:
            raise HTTPException(status_code=400, detail="이 메일에 연결된 초안이 없습니다. 먼저 답장을 생성하고 저장하세요.")

        comp = await conn.fetchrow(
            "SELECT * FROM mail_compositions WHERE id = $1", inbox["composition_id"]
        )
        if not comp:
            raise HTTPException(status_code=404, detail="초안을 찾을 수 없습니다")

    # 번역본이 있으면 번역본 발송, 없으면 한국어 초안
    body = comp["translated_draft"] if comp["translated_draft"] else comp["korean_draft"]
    if not body:
        raise HTTPException(status_code=400, detail="발송할 내용이 없습니다")

    try:
        await asyncio.to_thread(
            gmail_service.send_email,
            config["email"], config["app_password"],
            inbox["from_addr"], inbox["subject"] or "", body,
            reply_to_subject=inbox["subject"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"메일 발송 실패: {e}")

    # 상태 업데이트
    async with db.vector_pool.acquire() as conn:
        await conn.execute(
            "UPDATE inbox_emails SET status = 'replied' WHERE id = $1", inbox_id
        )

    return {"message": "메일 발송 완료"}


@router.post("/gmail/inbox/{inbox_id}/link")
async def gmail_link_composition(inbox_id: int, composition_id: int, _=Depends(verify_token)):
    """수신 메일에 초안(composition) 연결"""
    if not db.vector_pool:
        raise HTTPException(status_code=500, detail="DB 연결 없음")
    async with db.vector_pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE inbox_emails SET composition_id = $1, status = 'draft_ready' WHERE id = $2",
            composition_id, inbox_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="수신 메일을 찾을 수 없습니다")
    return {"message": "초안 연결 완료"}


# ============================================================
#  백그라운드 자동 체크 루프
# ============================================================

async def gmail_auto_check_loop():
    """매 60초마다 자동 체크 설정을 확인하고, 조건 충족 시 메일 fetch + 자동 초안 생성."""
    last_checked_date = None

    while True:
        try:
            await asyncio.sleep(60)

            if not db.vector_pool:
                continue

            async with db.vector_pool.acquire() as conn:
                config = await conn.fetchrow("SELECT * FROM gmail_config LIMIT 1")

            if not config or not config["auto_reply_enabled"]:
                continue

            now = datetime.now(timezone.utc)
            today_str = now.strftime("%Y-%m-%d")

            # 오늘 이미 체크했으면 skip
            if last_checked_date == today_str:
                continue

            # 현재 시각이 check_time 이전이면 skip
            check_time = config["check_time"] or "09:00"
            try:
                check_h, check_m = map(int, check_time.split(":"))
            except ValueError:
                check_h, check_m = 9, 0

            # UTC+9 (KST) 기준으로 비교
            kst_hour = (now.hour + 9) % 24
            kst_minute = now.minute
            if kst_hour < check_h or (kst_hour == check_h and kst_minute < check_m):
                continue

            print(f"[Gmail 자동 체크] 실행 중... ({today_str} {check_time})", flush=True)

            # 1. 새 메일 fetch
            since = config["last_checked_at"]
            emails = await asyncio.to_thread(
                gmail_service.fetch_new_emails, config["email"], config["app_password"], since
            )

            new_emails = []
            async with db.vector_pool.acquire() as conn:
                for em in emails:
                    exists = await conn.fetchval(
                        "SELECT 1 FROM inbox_emails WHERE gmail_uid = $1", em["uid"]
                    )
                    if exists:
                        continue
                    row = await conn.fetchrow(
                        """INSERT INTO inbox_emails (gmail_uid, from_addr, from_name, subject, body, received_at)
                           VALUES ($1, $2, $3, $4, $5, $6) RETURNING id""",
                        em["uid"], em["from_addr"], em["from_name"],
                        em["subject"], em["body"], em["received_at"],
                    )
                    new_emails.append({"inbox_id": row["id"], **em})

                await conn.execute(
                    "UPDATE gmail_config SET last_checked_at = $1",
                    datetime.now(timezone.utc),
                )

            # 2. 각 새 메일에 대해 자동 초안 생성
            for em in new_emails:
                try:
                    incoming_text = f"From: {em['from_name']} <{em['from_addr']}>\nSubject: {em['subject']}\n\n{em['body']}"

                    # RAG 검색
                    chunks = await search_similar_chunks(
                        query=incoming_text, top_k=8, purpose="rag_session"
                    )
                    references = [
                        {"filename": c["filename"], "chunk_text": c["chunk_text"], "similarity": round(c["similarity"], 4)}
                        for c in chunks if c["similarity"] > 0.25
                    ]

                    # AI 초안 생성
                    result = _generate_mail_draft(incoming_text, references, "formal")

                    # 번역
                    detected_lang = result.get("detected_lang", "en")
                    translated = ""
                    if detected_lang != "ko" and result["korean_draft"]:
                        translated = _translate_text(result["korean_draft"], detected_lang)

                    # mail_compositions에 저장
                    async with db.vector_pool.acquire() as conn:
                        comp_row = await conn.fetchrow(
                            """INSERT INTO mail_compositions
                               (incoming_email, detected_lang, tone, korean_draft, translated_draft, document_ids, refs)
                               VALUES ($1, $2, $3, $4, $5, '[]'::jsonb, $6::jsonb)
                               RETURNING id""",
                            incoming_text, detected_lang, "formal",
                            result["korean_draft"], translated,
                            json.dumps(references, ensure_ascii=False),
                        )
                        # inbox_emails 업데이트
                        await conn.execute(
                            "UPDATE inbox_emails SET composition_id = $1, status = 'draft_ready' WHERE id = $2",
                            comp_row["id"], em["inbox_id"],
                        )

                    print(f"[Gmail 자동 체크] 초안 생성 완료: {em['subject']}", flush=True)
                except Exception as e:
                    print(f"[Gmail 자동 체크] 초안 생성 실패 ({em['subject']}): {e}", flush=True)

            last_checked_date = today_str
            print(f"[Gmail 자동 체크] 완료 — 새 메일 {len(new_emails)}건 처리", flush=True)

        except asyncio.CancelledError:
            print("[Gmail 자동 체크] 종료", flush=True)
            break
        except Exception as e:
            print(f"[Gmail 자동 체크] 오류: {e}", flush=True)
            await asyncio.sleep(60)


# ============================================================
#  AI 함수들
# ============================================================

def _translate_text(korean_text: str, target_lang: str) -> str:
    """한국어 텍스트를 대상 언어로 번역한다."""
    from decouple import config
    import google.genai as genai
    from google.genai import types

    api_key = config("GOOGLE_API_KEY", default="")
    if not api_key:
        return "API Key가 설정되지 않았습니다."

    lang_names = {
        "en": "English",
        "ja": "Japanese (日本語)",
        "zh": "Chinese (中文)",
        "ko": "Korean (한국어)",
        "de": "German (Deutsch)",
        "fr": "French (Français)",
        "es": "Spanish (Español)",
    }
    lang_name = lang_names.get(target_lang, target_lang)

    system_prompt = f"""당신은 전문 비즈니스 번역가입니다.
아래 한국어 메일을 {lang_name}로 번역하세요.

## 규칙
- 비즈니스 메일에 적합한 격식체 사용
- 기술 용어(부품명, 사양 등)는 해당 업계 표준 표현 사용
- 회사명 "영마린테크"는 "Young Marine Tech"로 표기
- "[확인 필요]" 같은 메모는 번역 언어에 맞게 변환 (예: [To be confirmed])
- 번역문만 출력 (설명이나 메모 없이)
"""

    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[{"role": "user", "parts": [{"text": korean_text}]}],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.3,
            ),
        )
        return response.text
    except Exception as e:
        print(f"번역 오류: {e}", flush=True)
        return f"번역 중 오류가 발생했습니다: {e}"
