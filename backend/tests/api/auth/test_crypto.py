import base64
import os
from uuid import uuid4

import pytest
from cryptography.exceptions import InvalidTag
from kwak_api.auth.crypto import SecretBox
from kwak_api.settings import Settings
from pydantic import ValidationError

KEY = os.urandom(32)


def test_roundtrip_with_a_fresh_nonce_each_time() -> None:
    box, owner = SecretBox(KEY), uuid4()
    first, second = box.encrypt(b"secret", owner), box.encrypt(b"secret", owner)
    assert first != second
    assert box.decrypt(first, owner) == b"secret"


def test_ciphertext_is_bound_to_its_owner() -> None:
    box = SecretBox(KEY)
    sealed = box.encrypt(b"secret", uuid4())
    with pytest.raises(InvalidTag):
        box.decrypt(sealed, uuid4())


def test_tampering_or_a_wrong_key_is_detected() -> None:
    owner = uuid4()
    sealed = SecretBox(KEY).encrypt(b"secret", owner)
    tampered = sealed[:-1] + bytes([sealed[-1] ^ 1])
    with pytest.raises(InvalidTag):
        SecretBox(KEY).decrypt(tampered, owner)
    with pytest.raises(InvalidTag):
        SecretBox(os.urandom(32)).decrypt(sealed, owner)


def test_settings_require_a_secret_key_outside_dev() -> None:
    with pytest.raises(ValidationError, match="KWAK_SECRET_KEY"):
        Settings(env="prod", secret_key=None)


def test_settings_reject_a_key_that_is_not_32_bytes() -> None:
    short = base64.urlsafe_b64encode(os.urandom(16)).decode()
    with pytest.raises(ValidationError, match="32 bytes"):
        Settings(secret_key=short)


def test_settings_decode_the_key() -> None:
    assert Settings(secret_key=base64.urlsafe_b64encode(KEY).decode()).encryption_key == KEY
    assert len(Settings(env="dev", secret_key=None).encryption_key) == 32


def test_settings_default_to_prod_so_a_missing_env_never_falls_back_to_the_dev_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KWAK_ENV", raising=False)
    monkeypatch.delenv("KWAK_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError, match="KWAK_SECRET_KEY"):
        Settings(_env_file=None)
