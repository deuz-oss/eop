from datetime import UTC, datetime, timedelta

from starlette.requests import Request

from eop_api.core import login_throttle as throttle_module
from eop_api.core.login_throttle import (
    ACCOUNT_FAILURE_THRESHOLD,
    IP_FAILURE_THRESHOLD,
    LoginThrottle,
    _delay_for,  # testing the capped-exponent fix directly
    account_key,
    client_ip_key,
)


def _make_request(
    *, client: tuple[str, int] | None, headers: list[tuple[bytes, bytes]] | None = None
) -> Request:
    return Request({"type": "http", "client": client, "headers": headers or []})


def test_account_key_normalizes_case_and_whitespace():
    assert account_key(" Ada@Example.com ") == account_key("ada@example.com")
    assert account_key("ada@example.com") == "ada@example.com"


def test_client_ip_key_ignores_forwarded_headers():
    request = _make_request(client=("9.9.9.9", 12345), headers=[(b"x-forwarded-for", b"1.2.3.4")])

    assert client_ip_key(request) == "9.9.9.9"


def test_client_ip_key_handles_missing_client():
    request = _make_request(client=None)

    assert client_ip_key(request) == "unknown"


def test_client_ip_key_supports_ipv6():
    request = _make_request(client=("2001:db8::1", 12345))

    assert client_ip_key(request) == "2001:db8::1"


def test_is_account_throttled_and_is_ip_throttled_are_independent():
    throttle = LoginThrottle()
    for _ in range(ACCOUNT_FAILURE_THRESHOLD):
        throttle.record_failure(account_key="a@example.com", ip_key="1.1.1.1")

    # The account dimension alone reports throttled...
    assert throttle.is_account_throttled("a@example.com") is True
    # ...while the IP dimension, checked in isolation, does not -- it takes
    # IP_FAILURE_THRESHOLD (30) failures, not ACCOUNT_FAILURE_THRESHOLD (5), to trip.
    assert throttle.is_ip_throttled("1.1.1.1") is False
    # And the combined check still reflects either dimension being over threshold.
    assert throttle.is_throttled(account_key="a@example.com", ip_key="1.1.1.1") is True


def test_first_five_account_failures_are_not_throttled():
    throttle = LoginThrottle()

    for _ in range(ACCOUNT_FAILURE_THRESHOLD):
        assert throttle.is_throttled(account_key="a@example.com", ip_key="1.1.1.1") is False
        delay = throttle.record_failure(account_key="a@example.com", ip_key="1.1.1.1")
        assert delay == 0.0

    assert throttle.is_throttled(account_key="a@example.com", ip_key="1.1.1.1") is True


def test_account_backoff_curve_matches_locked_policy():
    throttle = LoginThrottle()
    for _ in range(ACCOUNT_FAILURE_THRESHOLD):
        throttle.record_failure(account_key="a@example.com", ip_key="1.1.1.1")

    expected_delays = [1.0, 2.0, 4.0, 8.0, 16.0, 16.0]
    actual_delays = [
        throttle.record_failure(account_key="a@example.com", ip_key="1.1.1.1")
        for _ in expected_delays
    ]

    assert actual_delays == expected_delays


def test_ip_threshold_matches_locked_policy():
    throttle = LoginThrottle()

    for i in range(IP_FAILURE_THRESHOLD):
        key = f"user{i}@example.com"
        assert throttle.is_throttled(account_key=key, ip_key="2.2.2.2") is False
        throttle.record_failure(account_key=key, ip_key="2.2.2.2")

    never_attempted = "never-attempted@example.com"
    assert throttle.is_throttled(account_key=never_attempted, ip_key="2.2.2.2") is True


def test_account_attacked_from_many_ips_is_still_protected():
    throttle = LoginThrottle()

    for i in range(ACCOUNT_FAILURE_THRESHOLD):
        throttle.record_failure(account_key="victim@example.com", ip_key=f"10.0.0.{i}")

    assert throttle.is_throttled(account_key="victim@example.com", ip_key="10.0.0.99") is True
    # None of the individual attacking IPs crossed the (much higher) IP threshold on its own.
    assert throttle.is_throttled(account_key="someone-else@example.com", ip_key="10.0.0.0") is False


def test_one_ip_attacking_many_accounts_is_still_protected():
    throttle = LoginThrottle()

    for i in range(IP_FAILURE_THRESHOLD):
        throttle.record_failure(account_key=f"target{i}@example.com", ip_key="3.3.3.3")

    assert throttle.is_throttled(account_key="fresh-target@example.com", ip_key="3.3.3.3") is True
    # No single targeted account crossed its own (much lower) account threshold.
    assert throttle.is_throttled(account_key="target0@example.com", ip_key="9.9.9.9") is False


def test_successful_login_resets_account_but_not_ip():
    throttle = LoginThrottle()
    for _ in range(IP_FAILURE_THRESHOLD):
        throttle.record_failure(account_key="victim@example.com", ip_key="4.4.4.4")

    assert throttle.is_throttled(account_key="victim@example.com", ip_key="0.0.0.0") is True

    throttle.record_success(account_key="victim@example.com")

    assert throttle.is_throttled(account_key="victim@example.com", ip_key="0.0.0.0") is False
    # The IP dimension is untouched by the account-scoped reset.
    other_account = "another-account@example.com"
    assert throttle.is_throttled(account_key=other_account, ip_key="4.4.4.4") is True


def test_account_state_expires_after_fifteen_minutes_of_inactivity(monkeypatch):
    throttle = LoginThrottle()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    monkeypatch.setattr(throttle_module, "_now", lambda: start)

    for _ in range(ACCOUNT_FAILURE_THRESHOLD):
        throttle.record_failure(account_key="a@example.com", ip_key="1.1.1.1")
    assert throttle.is_throttled(account_key="a@example.com", ip_key="1.1.1.1") is True

    monkeypatch.setattr(throttle_module, "_now", lambda: start + timedelta(minutes=15, seconds=1))

    assert throttle.is_throttled(account_key="a@example.com", ip_key="1.1.1.1") is False
    # The first failure after expiry starts a fresh count, not a continuation.
    delay = throttle.record_failure(account_key="a@example.com", ip_key="1.1.1.1")
    assert delay == 0.0


def test_account_state_survives_within_the_window(monkeypatch):
    throttle = LoginThrottle()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    monkeypatch.setattr(throttle_module, "_now", lambda: start)

    for _ in range(ACCOUNT_FAILURE_THRESHOLD):
        throttle.record_failure(account_key="a@example.com", ip_key="1.1.1.1")

    monkeypatch.setattr(throttle_module, "_now", lambda: start + timedelta(minutes=14, seconds=59))

    assert throttle.is_throttled(account_key="a@example.com", ip_key="1.1.1.1") is True


def test_delay_for_does_not_overflow_at_extreme_failure_counts():
    # `2.0 ** x` overflows once `x >= 1024`; a failure_count this large is what an
    # attacker hammering a key continuously (never letting its window expire)
    # could eventually reach. This must not raise, and must still return exactly
    # the capped maximum.
    huge_failure_count = 10_000_000

    delay = _delay_for(huge_failure_count, ACCOUNT_FAILURE_THRESHOLD)

    assert delay == 16.0


def test_delay_for_preserves_existing_backoff_curve():
    # The overflow fix must not change any value on the actual backoff curve.
    threshold = ACCOUNT_FAILURE_THRESHOLD
    expected = {
        threshold: 0.0,
        threshold + 1: 1.0,
        threshold + 2: 2.0,
        threshold + 3: 4.0,
        threshold + 4: 8.0,
        threshold + 5: 16.0,
        threshold + 6: 16.0,
    }

    for failure_count, expected_delay in expected.items():
        assert _delay_for(failure_count, threshold) == expected_delay
