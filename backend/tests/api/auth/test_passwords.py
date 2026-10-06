from kwak_api.auth.passwords import hash_password, needs_rehash, verify_password


def test_hash_uses_argon2id_and_a_random_salt() -> None:
    first, second = hash_password("correct horse"), hash_password("correct horse")
    assert first.startswith("$argon2id$")
    assert first != second


def test_verify_accepts_the_right_password_only() -> None:
    hashed = hash_password("correct horse")
    assert verify_password(hashed, "correct horse")
    assert not verify_password(hashed, "wrong horse")


def test_verify_rejects_a_malformed_hash() -> None:
    assert not verify_password("not-a-hash", "correct horse")


def test_needs_rehash_flags_weaker_parameters() -> None:
    weak = "$argon2id$v=19$m=8,t=1,p=1$c29tZXNhbHQ$9sTbSlTio3Biev89thdrlKKiCaYsjjYVJxGAL3swxpQ"
    assert needs_rehash(weak)
    assert not needs_rehash(hash_password("correct horse"))
