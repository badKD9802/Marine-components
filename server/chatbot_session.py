"""인메모리 채팅 세션 관리."""
import time
import uuid
from typing import Optional


class ChatSession:
    """단일 채팅 세션."""

    def __init__(self, session_id: str = None, title: str = "새 대화"):
        self.session_id = session_id or str(uuid.uuid4())
        self.title = title
        self.messages = []  # [{"role": "user"|"assistant", "content": "..."}]
        self.created_at = time.time()
        self.updated_at = time.time()

    def append(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self.updated_at = time.time()
        # 첫 사용자 메시지로 제목 설정
        if role == "user" and self.title == "새 대화":
            self.title = content[:30] + ("..." if len(content) > 30 else "")

    def get_history(self):
        return list(self.messages)

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "title": self.title,
            "message_count": len(self.messages),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class SessionManager:
    """인메모리 세션 관리자. TTL 24시간, 최대 100개."""

    MAX_SESSIONS = 100
    TTL_SECONDS = 86400  # 24시간

    def __init__(self):
        self._sessions: dict[str, ChatSession] = {}

    def create(self, title: str = "새 대화") -> ChatSession:
        self._cleanup()
        session = ChatSession(title=title)
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Optional[ChatSession]:
        session = self._sessions.get(session_id)
        if session and (time.time() - session.created_at) > self.TTL_SECONDS:
            del self._sessions[session_id]
            return None
        return session

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_all(self) -> list[dict]:
        self._cleanup()
        sessions = sorted(
            self._sessions.values(), key=lambda s: s.updated_at, reverse=True
        )
        return [s.to_dict() for s in sessions]

    def _cleanup(self):
        """만료 세션 제거 + 최대 개수 초과 시 오래된 것부터 삭제."""
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if (now - s.created_at) > self.TTL_SECONDS
        ]
        for sid in expired:
            del self._sessions[sid]

        if len(self._sessions) >= self.MAX_SESSIONS:
            sorted_sessions = sorted(
                self._sessions.items(), key=lambda x: x[1].updated_at
            )
            to_remove = len(self._sessions) - self.MAX_SESSIONS + 1
            for sid, _ in sorted_sessions[:to_remove]:
                del self._sessions[sid]


# 전역 싱글톤
session_manager = SessionManager()
