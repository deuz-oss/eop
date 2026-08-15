"""Process-local, in-memory login-abuse throttle for `POST /auth/login`.

Two independent counters guard the endpoint -- one keyed by the attempted
account email, one by the client IP -- each applying the same progressive
backoff once its own failure threshold is crossed within a sliding 15-minute
window. A counter's window slides forward on every new failure and expires
(resets to zero) once 15 minutes pass with no further failures against that
key.

This is deliberately a single concrete, non-swappable component: state lives
only in this process, is never persisted, and does not survive a restart or
get shared across multiple API instances. That is a locked v1 policy
decision (see docs/architecture Phase 8/8A discovery), not an oversight --
it does not use Redis or any other external store, and must be revisited
only if the deployment topology becomes horizontally scaled.
"""

import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Request

_WINDOW = timedelta(minutes=15)
_MAX_DELAY_SECONDS = 16.0

ACCOUNT_FAILURE_THRESHOLD = 5
IP_FAILURE_THRESHOLD = 30


def _now() -> datetime:
    return datetime.now(UTC)


def _delay_for(failure_count: int, threshold: int) -> float:
    """Progressive backoff: 0 at/under `threshold`, then 1s, 2s, 4s, 8s, capped at 16s.

    The exponent is capped before exponentiation, not after: `2.0 ** x` overflows
    once `x >= 1024`, which an arbitrarily large `failure_count` could otherwise
    reach if a key is attacked continuously enough to never let its window expire.
    Capping the exponent to a value that's already far past where the result
    would clamp to `_MAX_DELAY_SECONDS` anyway keeps this overflow-free for any
    `failure_count`, while leaving the actual 1s/2s/4s/8s/16s curve unchanged.
    """
    overage = failure_count - threshold
    if overage <= 0:
        return 0.0
    capped_exponent = min(overage - 1, 30)
    return min(2.0**capped_exponent, _MAX_DELAY_SECONDS)


@dataclass
class _Counter:
    failure_count: int
    last_failure_at: datetime


class _KeyedThrottle:
    """Independent per-key failure counters sharing one threshold and window."""

    def __init__(self, *, threshold: int) -> None:
        self._threshold = threshold
        self._counters: dict[str, _Counter] = {}
        self._lock = threading.Lock()

    def _active_count_locked(self, key: str, now: datetime) -> int:
        counter = self._counters.get(key)
        if counter is None or now - counter.last_failure_at > _WINDOW:
            return 0
        return counter.failure_count

    def is_throttled(self, key: str) -> bool:
        with self._lock:
            return self._active_count_locked(key, _now()) >= self._threshold

    def record_failure(self, key: str) -> float:
        """Records one failure for `key` and returns the delay now in effect."""
        now = _now()
        with self._lock:
            count = self._active_count_locked(key, now) + 1
            self._counters[key] = _Counter(failure_count=count, last_failure_at=now)
            return _delay_for(count, self._threshold)

    def clear(self, key: str) -> None:
        with self._lock:
            self._counters.pop(key, None)

    def reset_all(self) -> None:
        """Test-only: clears every key. Never called from request handling."""
        with self._lock:
            self._counters.clear()


class LoginThrottle:
    """Combines the account-scoped and IP-scoped counters guarding `/auth/login`."""

    def __init__(self) -> None:
        self._account = _KeyedThrottle(threshold=ACCOUNT_FAILURE_THRESHOLD)
        self._ip = _KeyedThrottle(threshold=IP_FAILURE_THRESHOLD)

    def is_throttled(self, *, account_key: str, ip_key: str) -> bool:
        """Whether a request against either key would currently be rejected.

        Read-only: does not record an attempt. Callers that reject a request
        based on this must still call `record_failure` for it.
        """
        return self._account.is_throttled(account_key) or self._ip.is_throttled(ip_key)

    def is_account_throttled(self, account_key: str) -> bool:
        """The account dimension only, read-only. Lets a caller distinguish
        "this account is over its own threshold" from "this IP is" so it can
        apply different handling to each (e.g. still evaluate credentials for
        an account-throttled request, to allow a correct password through)."""
        return self._account.is_throttled(account_key)

    def is_ip_throttled(self, ip_key: str) -> bool:
        """The IP dimension only, read-only. See `is_account_throttled`."""
        return self._ip.is_throttled(ip_key)

    def record_failure(self, *, account_key: str, ip_key: str) -> float:
        """Records a failure against both keys; returns the resulting Retry-After delay."""
        account_delay = self._account.record_failure(account_key)
        ip_delay = self._ip.record_failure(ip_key)
        return max(account_delay, ip_delay)

    def record_success(self, *, account_key: str) -> None:
        """Clears the account-scoped counter only. The IP-scoped counter never resets
        on success -- an attacker who eventually guesses correctly against one account
        does not regain a clean IP budget for attacking others."""
        self._account.clear(account_key)

    def reset_all(self) -> None:
        """Test-only: clears all account and IP state. Never called from request handling."""
        self._account.reset_all()
        self._ip.reset_all()


login_throttle = LoginThrottle()


def account_key(email: str) -> str:
    """Normalizes an attempted login email into a throttle key.

    Case-insensitive so an attacker cannot bypass the per-account threshold
    by varying the email's letter case across attempts.
    """
    return email.strip().lower()


def client_ip_key(request: Request) -> str:
    """The throttle's client-IP key: the direct ASGI/Starlette peer address only.

    Deliberately does not consult `X-Forwarded-For`, `X-Real-IP`, or any other
    forwarded header -- this repository has no evidence of a trusted proxy
    boundary, and trusting a client-settable header would let an attacker
    forge a distinct value per request and defeat IP-scoped throttling
    entirely. Revisit only alongside a confirmed deployment-topology decision.
    """
    if request.client is None:
        return "unknown"
    return request.client.host
