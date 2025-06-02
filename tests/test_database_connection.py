import pytest
from sqlalchemy.engine import Engine

from discharge_docs.database.connection import get_connection_string, get_engine


def test_get_connection_string_default(monkeypatch):
    monkeypatch.setenv("DB_USER", "user")
    monkeypatch.setenv("DB_PASSWD", "pass")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "1433")
    monkeypatch.setenv("DB_DATABASE", "testdb")

    conn_str, exec_opts = get_connection_string()
    assert "mssql+pymssql://user:pass@localhost:1433/testdb" == conn_str
    assert exec_opts is None


def test_get_connection_string_acc(monkeypatch):
    monkeypatch.setenv("DB_USER", "user")
    monkeypatch.setenv("DB_PASSWD", "pass")
    monkeypatch.setenv("DB_PORT", "1433")
    monkeypatch.setenv("DB_HOST_ACC", "acchost")
    monkeypatch.setenv("DB_DATABASE_ACC", "accdb")

    conn_str, exec_opts = get_connection_string(env="ACC")
    assert "mssql+pymssql://user:pass@acchost:1433/accdb" == conn_str
    assert exec_opts is None


def test_get_connection_string_prod(monkeypatch):
    monkeypatch.setenv("DB_USER", "user")
    monkeypatch.setenv("DB_PASSWD", "pass")
    monkeypatch.setenv("DB_PORT", "1433")
    monkeypatch.setenv("DB_HOST_PROD", "prodhost")
    monkeypatch.setenv("DB_DATABASE_PROD", "proddb")

    conn_str, exec_opts = get_connection_string(env="PROD")
    assert "mssql+pymssql://user:pass@prodhost:1433/proddb" == conn_str
    assert exec_opts is None


def test_get_connection_string_sqlite(monkeypatch):
    monkeypatch.setenv("DB_USER", "")
    conn_str, exec_opts = get_connection_string()
    assert conn_str.startswith("sqlite:///")
    assert isinstance(exec_opts, dict)


def test_get_connection_string_invalid_env():
    with pytest.raises(ValueError):
        get_connection_string(env="INVALID")


def test_get_engine_sqlite(monkeypatch):
    monkeypatch.setenv("DB_USER", "")
    engine = get_engine()
    assert isinstance(engine, Engine)
    assert str(engine.url).startswith("sqlite:///")
