# tests/integration/test_query_executor_sql.py
import pytest
from agent.services.query_executor import QueryExecutor
from sqlalchemy.exc import SQLAlchemyError

@pytest.mark.asyncio
async def test_run_sql_select_success(test_db):
    """
    Проверяет успешное выполнение корректного SELECT-запроса.
    """
    query_executor = QueryExecutor()
    sql_code = "SELECT username FROM users WHERE id = 1;"
    result = await query_executor.run_sql(sql_code)
    
    assert result["status"] == "success"
    assert result["result"]["columns"] == ["username"]
    assert result["result"]["rows"] == [["testuser1"]]

@pytest.mark.asyncio
async def test_run_sql_unsafe_query_permission_error(test_db):
    """
    Проверяет, что попытка выполнить небезопасный запрос (UPDATE)
    возвращает ошибку PERMISSION_ERROR.
    """
    query_executor = QueryExecutor()
    sql_code = "UPDATE users SET username = 'hacked' WHERE id = 1;"
    result = await query_executor.run_sql(sql_code)
    
    assert result["status"] == "error"
    assert result["error"]["type"] == "PERMISSION_ERROR"
    assert "Разрешены только запросы на чтение данных" in result["error"]["message"]


@pytest.mark.asyncio
async def test_run_sql_syntax_error_returns_db_error(test_db):
    """
    Проверяет, что синтаксически неверный SQL-запрос
    возвращает ошибку типа DATABASE_ERROR.
    """
    query_executor = QueryExecutor()
    sql_code = "SELECT FROM users;" # Неверный синтаксис
    
    result = await query_executor.run_sql(sql_code)
    
    assert result["status"] == "error"
    assert result["error"]["type"] == "DATABASE_ERROR"
