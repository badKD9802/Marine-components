"""DB 기반 채팅 세션 관리. (fallback: 인메모리)"""
import time
import uuid
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SessionManager:
    """asyncpg DB를 사용하는 세션 관리자. DB 없으면 인메모리 fallback."""

    MAX_SESSIONS = 100

    def __init__(self):
        self._memory: dict[str, dict] = {}  # fallback용

    def _get_pool(self):
        """db.py의 pool을 가져옴 (순환 import 방지)."""
        try:
            from db import pool
            return pool
        except ImportError:
            return None

    async def create(self, title: str = "새 대화") -> dict:
        """새 세션 생성. dict 반환: {session_id, title, created_at, updated_at}"""
        session_id = str(uuid.uuid4())
        pool = self._get_pool()

        if pool:
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow("""
                        INSERT INTO chatbot_sessions (session_id, title)
                        VALUES ($1, $2)
                        RETURNING session_id, title,
                                  EXTRACT(EPOCH FROM created_at) as created_at,
                                  EXTRACT(EPOCH FROM updated_at) as updated_at
                    """, session_id, title)
                    return {
                        "session_id": row["session_id"],
                        "title": row["title"],
                        "message_count": 0,
                        "created_at": float(row["created_at"]),
                        "updated_at": float(row["updated_at"]),
                    }
            except Exception as e:
                logger.warning(f"DB create 실패, 인메모리 fallback: {e}")

        # 인메모리 fallback
        now = time.time()
        session = {
            "session_id": session_id,
            "title": title,
            "message_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        self._memory[session_id] = {**session, "messages": []}
        return session

    async def get(self, session_id: str) -> Optional[dict]:
        """세션 조회. 없으면 None."""
        pool = self._get_pool()

        if pool:
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow("""
                        SELECT session_id, title,
                               EXTRACT(EPOCH FROM created_at) as created_at,
                               EXTRACT(EPOCH FROM updated_at) as updated_at
                        FROM chatbot_sessions WHERE session_id = $1
                    """, session_id)
                    if not row:
                        return None
                    msg_count = await conn.fetchval(
                        "SELECT COUNT(*) FROM chatbot_messages WHERE session_id = $1",
                        session_id
                    )
                    return {
                        "session_id": row["session_id"],
                        "title": row["title"],
                        "message_count": msg_count,
                        "created_at": float(row["created_at"]),
                        "updated_at": float(row["updated_at"]),
                    }
            except Exception as e:
                logger.warning(f"DB get 실패, 인메모리 fallback: {e}")

        # 인메모리 fallback
        mem = self._memory.get(session_id)
        if not mem:
            return None
        return {k: v for k, v in mem.items() if k != "messages"}

    async def get_history(self, session_id: str) -> list[dict]:
        """세션의 메시지 히스토리 반환."""
        pool = self._get_pool()

        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch("""
                        SELECT role, content FROM chatbot_messages
                        WHERE session_id = $1 ORDER BY id
                    """, session_id)
                    return [{"role": r["role"], "content": r["content"]} for r in rows]
            except Exception as e:
                logger.warning(f"DB get_history 실패, 인메모리 fallback: {e}")

        # 인메모리 fallback
        mem = self._memory.get(session_id)
        return list(mem["messages"]) if mem else []

    async def append(self, session_id: str, role: str, content: str):
        """메시지 추가. 첫 user 메시지일 때 제목 자동 설정."""
        pool = self._get_pool()

        if pool:
            try:
                async with pool.acquire() as conn:
                    # 메시지 삽입
                    await conn.execute("""
                        INSERT INTO chatbot_messages (session_id, role, content)
                        VALUES ($1, $2, $3)
                    """, session_id, role, content)

                    # updated_at 갱신
                    await conn.execute("""
                        UPDATE chatbot_sessions SET updated_at = NOW()
                        WHERE session_id = $1
                    """, session_id)

                    # 첫 user 메시지로 제목 자동 설정
                    if role == "user":
                        current = await conn.fetchrow("""
                            SELECT title FROM chatbot_sessions WHERE session_id = $1
                        """, session_id)
                        if current and current["title"] == "새 대화":
                            new_title = content[:30] + ("..." if len(content) > 30 else "")
                            await conn.execute("""
                                UPDATE chatbot_sessions SET title = $1
                                WHERE session_id = $2
                            """, new_title, session_id)
                    return
            except Exception as e:
                logger.warning(f"DB append 실패, 인메모리 fallback: {e}")

        # 인메모리 fallback
        mem = self._memory.get(session_id)
        if mem:
            mem["messages"].append({"role": role, "content": content})
            mem["updated_at"] = time.time()
            mem["message_count"] = len(mem["messages"])
            if role == "user" and mem["title"] == "새 대화":
                mem["title"] = content[:30] + ("..." if len(content) > 30 else "")

    async def delete(self, session_id: str) -> bool:
        """세션 삭제."""
        pool = self._get_pool()

        if pool:
            try:
                async with pool.acquire() as conn:
                    result = await conn.execute(
                        "DELETE FROM chatbot_sessions WHERE session_id = $1",
                        session_id
                    )
                    return result != "DELETE 0"
            except Exception as e:
                logger.warning(f"DB delete 실패, 인메모리 fallback: {e}")

        # 인메모리 fallback
        if session_id in self._memory:
            del self._memory[session_id]
            return True
        return False

    async def list_all(self) -> list[dict]:
        """모든 세션 목록 (최신순)."""
        pool = self._get_pool()

        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch("""
                        SELECT s.session_id, s.title,
                               EXTRACT(EPOCH FROM s.created_at) as created_at,
                               EXTRACT(EPOCH FROM s.updated_at) as updated_at,
                               COUNT(m.id) as message_count
                        FROM chatbot_sessions s
                        LEFT JOIN chatbot_messages m ON s.session_id = m.session_id
                        GROUP BY s.id, s.session_id, s.title, s.created_at, s.updated_at
                        ORDER BY s.updated_at DESC
                        LIMIT $1
                    """, self.MAX_SESSIONS)
                    return [{
                        "session_id": r["session_id"],
                        "title": r["title"],
                        "message_count": r["message_count"],
                        "created_at": float(r["created_at"]),
                        "updated_at": float(r["updated_at"]),
                    } for r in rows]
            except Exception as e:
                logger.warning(f"DB list_all 실패, 인메모리 fallback: {e}")

        # 인메모리 fallback
        sessions = sorted(
            self._memory.values(), key=lambda s: s["updated_at"], reverse=True
        )
        return [{k: v for k, v in s.items() if k != "messages"} for s in sessions[:self.MAX_SESSIONS]]


# 전역 싱글톤
session_manager = SessionManager()
