import pytest

from journ.db import Database


@pytest.fixture
def db(tmp_path):
    with Database(tmp_path / "journal.db") as database:
        yield database


@pytest.fixture
def fake_keyring(monkeypatch):
    """Dict-backed stand-in for the OS credential store, so tests never touch a real one."""
    import keyring
    import keyring.errors

    store: dict[tuple[str, str], str] = {}

    def fake_set(service, username, password):
        store[(service, username)] = password

    def fake_get(service, username):
        return store.get((service, username))

    def fake_delete(service, username):
        if (service, username) not in store:
            raise keyring.errors.PasswordDeleteError("not found")
        del store[(service, username)]

    monkeypatch.setattr(keyring, "set_password", fake_set)
    monkeypatch.setattr(keyring, "get_password", fake_get)
    monkeypatch.setattr(keyring, "delete_password", fake_delete)
    return store
