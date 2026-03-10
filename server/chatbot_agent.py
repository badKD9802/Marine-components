"""AI 챗봇 ReAct Agent — FastAPI 라우터."""
import asyncio
import json
import logging
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional

from chatbot_session import session_manager
from chatbot_sse import SSEWriter, format_sse
from chatbot_llm import LLMClient
from react_system.auth_context import AuthContext
from react_system.react_agent import ReactAgent
from react_system.tool_registry import ToolRegistry
from react_system.tool_definitions import TOOLS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["chatbot"])


# --- Request/Response Models ---

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class SessionCreate(BaseModel):
    title: str = "새 대화"


# --- LLM Client Singleton ---

_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


# --- SSE Streaming ---

async def run_agent_stream(message: str, session_id: str, queue: asyncio.Queue):
    """ReAct 에이전트를 실행하고 결과를 SSE 큐로 전송."""
    try:
        session = session_manager.get(session_id)
        if not session:
            queue.put_nowait(("error", {"message": "세션을 찾을 수 없습니다."}))
            return

        # 사용자 메시지 저장
        session.append("user", message)

        # ReAct Agent 생성
        llm = get_llm_client()
        auth = AuthContext.demo()
        writer = SSEWriter(queue)
        registry = ToolRegistry(auth=auth)

        agent = ReactAgent(
            just_llm=llm,
            tool_registry=registry,
            tools=TOOLS,
            writer=writer,
        )

        # 에이전트 실행
        history = session.get_history()
        result = await agent.run(message, history=history)
        answer = result.get("answer", "")

        # 응답 저장
        session.append("assistant", answer)

        # 완료 이벤트
        queue.put_nowait(("done", {
            "session_id": session_id,
            "answer": answer,
        }))

    except Exception as e:
        logger.exception("Agent execution error")
        queue.put_nowait(("error", {"message": str(e)}))
    finally:
        queue.put_nowait(None)  # 스트림 종료 신호


async def sse_generator(queue: asyncio.Queue):
    """asyncio.Queue에서 SSE 이벤트를 읽어 스트리밍."""
    try:
        while True:
            item = await asyncio.wait_for(queue.get(), timeout=300)
            if item is None:
                break
            event_type, data = item
            yield format_sse(event_type, data)
    except asyncio.TimeoutError:
        yield format_sse("error", {"message": "Timeout"})


# --- Endpoints ---

@router.post("/chat")
async def chat_stream(request: ChatRequest):
    """SSE 스트리밍으로 AI 챗봇 응답."""
    # 세션 자동 생성
    if request.session_id:
        session = session_manager.get(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    else:
        session = session_manager.create()

    queue = asyncio.Queue()

    # 백그라운드에서 에이전트 실행
    asyncio.create_task(run_agent_stream(request.message, session.session_id, queue))

    return StreamingResponse(
        sse_generator(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-Id": session.session_id,
        },
    )


@router.post("/sessions")
async def create_session(request: SessionCreate = SessionCreate()):
    """새 채팅 세션 생성."""
    session = session_manager.create(title=request.title)
    return session.to_dict()


@router.get("/sessions")
async def list_sessions():
    """모든 세션 목록."""
    return session_manager.list_all()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """세션 상세 (메시지 포함)."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    data = session.to_dict()
    data["messages"] = session.get_history()
    return data


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """세션 삭제."""
    if not session_manager.delete(session_id):
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    return {"ok": True}
