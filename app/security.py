"""
In-memory per-email login throttler.

Tracks failed login attempts and locks the account after N failures within a
rolling window. Single-process only — do not deploy behind multiple replicas
without external state (e.g. Redis). Adequate for the diploma scope.

Known limitation: per-email lockout means a malicious actor can lock a
legitimate user out by repeatedly failing with their email. Mitigations
(longer windows, CAPTCHA, per-IP combined keying) are out of scope.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock

from app.config import get_settings


@dataclass
class _Entry:
    failures: list[datetime] = field(default_factory=list)
    locked_until: datetime | None = None


class LoginThrottler:
    def __init__(self, max_attempts: int, window_seconds: int, lockout_seconds: int):
        self.max_attempts = max_attempts
        self.window = timedelta(seconds=window_seconds)
        self.lockout = timedelta(seconds=lockout_seconds)
        self._state: dict[str, _Entry] = defaultdict(_Entry)
        self._lock = Lock()

    @staticmethod
    def _normalize(key: str) -> str:
        return key.strip().lower()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def check(self, key: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds). retry_after_seconds is 0 when allowed."""
        key = self._normalize(key)
        with self._lock:
            entry = self._state.get(key)
            if entry is None:
                return True, 0
            now = self._now()
            if entry.locked_until is not None and entry.locked_until > now:
                return False, int((entry.locked_until - now).total_seconds()) + 1
            if entry.locked_until is not None and entry.locked_until <= now:
                entry.locked_until = None
                entry.failures.clear()
            return True, 0

    def record_failure(self, key: str) -> tuple[bool, int]:
        """Return (now_locked, lockout_seconds_or_attempts_remaining)."""
        key = self._normalize(key)
        with self._lock:
            now = self._now()
            entry = self._state[key]
            entry.failures = [t for t in entry.failures if now - t < self.window]
            entry.failures.append(now)
            if len(entry.failures) >= self.max_attempts:
                entry.locked_until = now + self.lockout
                entry.failures.clear()
                return True, int(self.lockout.total_seconds())
            return False, self.max_attempts - len(entry.failures)

    def record_success(self, key: str) -> None:
        key = self._normalize(key)
        with self._lock:
            self._state.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._state.clear()


_settings = get_settings()
login_throttler = LoginThrottler(
    max_attempts=_settings.login_max_attempts,
    window_seconds=_settings.login_window_seconds,
    lockout_seconds=_settings.login_lockout_seconds,
)
