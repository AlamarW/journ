import pytest

from journ.db import Database


@pytest.fixture
def db(tmp_path):
    with Database(tmp_path / "journal.db") as database:
        yield database
