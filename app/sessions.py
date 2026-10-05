"""Session store.

No user accounts or persistent history. Sessions live in memory for the active
session only, expire server-side after a maximum lifetime, and are rejected on
every read/write once expired. Close-triggered deletion is best-effort and is
handled by the app layer when a browser signals it.
"""

from __future__ import annotations

import secrets
import threading
import time
from typing import Dict, List, Optional

from app.model import BusinessProfile, GrillTurn, Report


class Session:
    """Per-user conversation state for one planning session."""

    def __init__(self, session_id: str, max_age: int) -> None:
        self.id = session_id
        self.created_at = time.time()
        self.last_activity = time.time()
        self.max_age = max_age
        self.opening: str = ""
        self.profile: Optional[BusinessProfile] = None
        self.transcript: List[GrillTurn] = []
        self.report: Optional[Report] = None
        self.query_count = 0
        self.csrf_salt = secrets.token_hex(16)  # per-session CSRF salt

    @property
    def expired(self) -> bool:
        return time.time() - self.last_activity > self.max_age

    def touch(self) -> None:
        self.last_activity = time.time()

    def bump_queries(self, count: int = 1) -> None:
        self.query_count += count


class SessionStore:
    """Thread-safe in-memory session registry with expiry on access."""

    def __init__(self, max_age: int) -> None:
        self.max_age = max_age
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self) -> Session:
        session = Session(secrets.token_urlsafe(32), self.max_age)
        with self._lock:
            self._sessions[session.id] = session
        return session

    def get(self, session_id: Optional[str]) -> Optional[Session]:
        if not session_id:
            return None
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.expired:
                del self._sessions[session_id]
                return None
            session.touch()
            return session

    def delete(self, session_id: Optional[str]) -> None:
        if not session_id:
            return
        with self._lock:
            self._sessions.pop(session_id, None)

    def purge_expired(self) -> int:
        """Remove all expired sessions; returns how many were removed."""
        removed = 0
        with self._lock:
            expired = [sid for sid, s in self._sessions.items() if s.expired]
            for sid in expired:
                del self._sessions[sid]
                removed += 1
        return removed

    def size(self) -> int:
        with self._lock:
            return len(self._sessions)