"""Encryption at rest for small secrets (TOTP seeds), AES-256-GCM."""

import os
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_BYTES = 12


class SecretBox:
    def __init__(self, key: bytes) -> None:
        self._aead = AESGCM(key)

    def encrypt(self, plaintext: bytes, owner: UUID) -> bytes:
        """Nonce + ciphertext. `owner` is authenticated, so a copy to another row fails."""
        nonce = os.urandom(_NONCE_BYTES)
        return nonce + self._aead.encrypt(nonce, plaintext, owner.bytes)

    def decrypt(self, sealed: bytes, owner: UUID) -> bytes:
        """Raise `cryptography.exceptions.InvalidTag` on a wrong key, owner or tampering."""
        nonce, ciphertext = sealed[:_NONCE_BYTES], sealed[_NONCE_BYTES:]
        return self._aead.decrypt(nonce, ciphertext, owner.bytes)
