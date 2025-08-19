# tests/unit/test_config.py
import pytest
from agent.config import AgentSettings

def test_database_url_generation_postgres(monkeypatch):
    """
    Проверяет корректную сборку DATABASE_URL для PostgreSQL
    с использованием стандартных настроек.
    """
    monkeypatch.setenv("DB_DIALECT", "postgresql")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_USER", "user")
    monkeypatch.setenv("DB_PASSWORD", "password")
    monkeypatch.setenv("DB_NAME", "testdb")
    monkeypatch.setenv("CORE_LOGIC_URL", "http://test")
    monkeypatch.setenv("AGENT_SECRET_TOKEN", "test")
    monkeypatch.setenv("AGENT_PUBLIC_URL", "http://test")
    
    settings = AgentSettings()
    expected_url = "postgresql+psycopg://user:password@localhost:5432/testdb?sslmode=prefer"
    assert settings.DATABASE_URL == expected_url

def test_database_url_with_ssl_mode(monkeypatch):
    """
    Проверяет, что параметр sslmode корректно добавляется в конец URL.
    """
    monkeypatch.setenv("DB_DIALECT", "postgresql")
    monkeypatch.setenv("DB_HOST", "db.example.com")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_USER", "user")
    monkeypatch.setenv("DB_PASSWORD", "password")
    monkeypatch.setenv("DB_NAME", "proddb")
    monkeypatch.setenv("DB_SSL_MODE", "require")
    monkeypatch.setenv("CORE_LOGIC_URL", "http://test")
    monkeypatch.setenv("AGENT_SECRET_TOKEN", "test")
    monkeypatch.setenv("AGENT_PUBLIC_URL", "http://test")

    settings = AgentSettings()
    expected_url = "postgresql+psycopg://user:password@db.example.com:5432/proddb?sslmode=require"
    assert settings.DATABASE_URL == expected_url

def test_database_url_with_special_chars_in_password(monkeypatch):
    """
    Проверяет, что пароль со специальными символами корректно кодируется.
    Символ @ должен быть закодирован как %40.
    """
    monkeypatch.setenv("DB_DIALECT", "postgresql")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_USER", "user")
    monkeypatch.setenv("DB_PASSWORD", "pass@word#123")
    monkeypatch.setenv("DB_NAME", "testdb")
    monkeypatch.setenv("CORE_LOGIC_URL", "http://test")
    monkeypatch.setenv("AGENT_SECRET_TOKEN", "test")
    monkeypatch.setenv("AGENT_PUBLIC_URL", "http://test")

    settings = AgentSettings()
    # quote_plus('pass@word#123') -> 'pass%40word%23123'
    expected_url = "postgresql+psycopg://user:pass%40word%23123@localhost:5432/testdb?sslmode=prefer"
    assert settings.DATABASE_URL == expected_url
