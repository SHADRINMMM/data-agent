# tests/unit/test_auth.py
import pytest
from fastapi import HTTPException
from agent.api import verify_token
from agent.config import settings

# Устанавливаем тестовый токен для всех тестов в этом файле
TEST_TOKEN = "test-secret-token"
settings.AGENT_SECRET_TOKEN = TEST_TOKEN

@pytest.mark.asyncio
async def test_verify_token_success():
    """
    Проверяет, что корректный токен 'Bearer <token>' проходит проверку.
    """
    # Должен выполниться без исключений
    await verify_token(f"Bearer {TEST_TOKEN}")

@pytest.mark.asyncio
async def test_verify_token_missing():
    """
    Проверяет, что при отсутствии токена выбрасывается HTTPException 401.
    """
    with pytest.raises(HTTPException) as exc_info:
        await verify_token(None)
    assert exc_info.value.status_code == 401
    assert "Требуется токен авторизации" in exc_info.value.detail

@pytest.mark.asyncio
async def test_verify_token_invalid_format_no_bearer():
    """
    Проверяет, что токен без префикса 'Bearer' не проходит.
    """
    with pytest.raises(HTTPException) as exc_info:
        await verify_token(TEST_TOKEN)
    assert exc_info.value.status_code == 401
    assert "Неверный формат токена" in exc_info.value.detail

@pytest.mark.asyncio
async def test_verify_token_invalid_format_wrong_scheme():
    """
    Проверяет, что токен с неверной схемой (не 'Bearer') не проходит.
    """
    with pytest.raises(HTTPException) as exc_info:
        await verify_token(f"Basic {TEST_TOKEN}")
    assert exc_info.value.status_code == 401
    assert "Неверный формат токена" in exc_info.value.detail

@pytest.mark.asyncio
async def test_verify_token_empty_token():
    """
    Проверяет, что пустой токен после 'Bearer ' не проходит.
    """
    with pytest.raises(HTTPException) as exc_info:
        await verify_token("Bearer ")
    assert exc_info.value.status_code == 401
    assert "Неверный формат токена" in exc_info.value.detail

@pytest.mark.asyncio
async def test_verify_token_incorrect_secret():
    """
    Проверяет, что с верным форматом, но неверным секретом, выбрасывается HTTPException 403.
    """
    with pytest.raises(HTTPException) as exc_info:
        await verify_token("Bearer wrong-secret")
    assert exc_info.value.status_code == 403
    assert "Неверный или недействительный токен" in exc_info.value.detail
