from journ import crypto


def test_round_trip():
    salt, canary = crypto.setup_passphrase("correct horse battery staple")
    key = crypto.verify_passphrase("correct horse battery staple", salt, canary)
    assert key is not None

    ciphertext = crypto.encrypt_text(key, "some very personal thoughts")
    assert crypto.decrypt_text(key, ciphertext) == "some very personal thoughts"


def test_ciphertext_is_not_plaintext():
    salt, canary = crypto.setup_passphrase("hunter2")
    key = crypto.verify_passphrase("hunter2", salt, canary)
    ciphertext = crypto.encrypt_text(key, "super personal entry")
    assert b"super personal entry" not in ciphertext


def test_wrong_passphrase_rejected():
    salt, canary = crypto.setup_passphrase("correct horse battery staple")
    assert crypto.verify_passphrase("wrong guess", salt, canary) is None


def test_different_salts_produce_different_keys():
    salt_a = crypto.generate_salt()
    salt_b = crypto.generate_salt()
    assert crypto.derive_key("same passphrase", salt_a) != crypto.derive_key(
        "same passphrase", salt_b
    )
