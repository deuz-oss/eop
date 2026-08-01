import time

import jwt
import pytest

from eop_api.core.config import settings
from eop_api.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_produces_different_hash_than_input():
    hashed = hash_password("correct-horse-battery-staple")

    assert hashed != "correct-horse-battery-staple"


def test_hash_password_is_salted():
    first = hash_password("correct-horse-battery-staple")
    second = hash_password("correct-horse-battery-staple")

    assert first != second


def test_verify_password_accepts_correct_password():
    hashed = hash_password("correct-horse-battery-staple")

    assert verify_password("correct-horse-battery-staple", hashed) is True


def test_verify_password_rejects_incorrect_password():
    hashed = hash_password("correct-horse-battery-staple")

    assert verify_password("wrong-password", hashed) is False


def test_create_access_token_returns_a_decodable_token():
    token = create_access_token(subject="user-123")

    payload = decode_access_token(token)

    assert payload["sub"] == "user-123"
    assert "exp" in payload


def test_create_access_token_payload_only_contains_sub_and_exp():
    token = create_access_token(subject="user-123")

    payload = decode_access_token(token)

    assert set(payload.keys()) == {"sub", "exp"}


def test_decode_access_token_rejects_malformed_token():
    with pytest.raises(jwt.PyJWTError):
        decode_access_token("not-a-valid-token")


def test_decode_access_token_rejects_expired_token():
    expired_payload = {"sub": "user-123", "exp": int(time.time()) - 60}
    token = jwt.encode(expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_decode_access_token_rejects_token_signed_with_different_secret():
    token = jwt.encode(
        {"sub": "user-123", "exp": int(time.time()) + 60},
        "a-different-secret-that-is-long-enough-for-hs256",
    )

    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)
