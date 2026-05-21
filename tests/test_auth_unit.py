from datetime import timedelta

import jwt
import pytest

from app.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password():
    h = hash_password("hunter2")
    assert h != "hunter2"
    assert verify_password("hunter2", h) is True
    assert verify_password("wrong", h) is False


def test_create_and_decode_token():
    token = create_access_token(subject="user-123")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"


def test_expired_token_rejected():
    token = create_access_token(subject="user-x", expires_delta=timedelta(seconds=-1))
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)
