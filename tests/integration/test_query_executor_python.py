# tests/integration/test_query_executor_python.py
import pytest
from agent.services.query_executor import QueryExecutor, SANDBOX_IMAGE_NAME
import docker

# --- Проверка наличия Docker-образа ---
try:
    docker_client = docker.from_env()
    docker_client.images.get(SANDBOX_IMAGE_NAME)
    DOCKER_IMAGE_PRESENT = True
except (docker.errors.ImageNotFound, docker.errors.DockerException):
    DOCKER_IMAGE_PRESENT = False

pytestmark = pytest.mark.skipif(not DOCKER_IMAGE_PRESENT, reason=f"Docker image {SANDBOX_IMAGE_NAME} not found. Run 'docker build ...' first.")

# --- Тесты ---

@pytest.mark.asyncio
async def test_run_python_happy_path(test_db):
    """
    Проверяет "счастливый путь":
    - Код выполняется в контейнере.
    - Подключается к БД.
    - Возвращает корректный DataFrame.
    """
    query_executor = QueryExecutor()
    python_code = """
import pandas as pd
import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"])

with get_db_connection() as con:
    df = pd.read_sql_query("SELECT name FROM products WHERE price > 100 ORDER BY name", con)
"""
    result = await query_executor.run_python(python_code)
    
    assert result["status"] == "success"
    assert result["result"]["columns"] == ["name"]
    assert result["result"]["rows"] == [["Laptop"]]

@pytest.mark.asyncio
async def test_run_python_no_df_variable_error(test_db):
    """
    Проверяет, что если код не создает переменную 'df',
    возвращается ошибка EXECUTION_ERROR.
    """
    query_executor = QueryExecutor()
    python_code = "x = 1 + 1" # Нет переменной df
    result = await query_executor.run_python(python_code)
    
    assert result["status"] == "error"
    assert result["error"]["type"] == "EXECUTION_ERROR"
    assert "не создал переменную 'df'" in result["error"]["message"]

@pytest.mark.asyncio
async def test_run_python_execution_exception_error(test_db):
    """
    Проверяет, что если код падает с исключением,
    ошибка корректно перехватывается.
    """
    query_executor = QueryExecutor()
    python_code = "1 / 0" # Деление на ноль
    result = await query_executor.run_python(python_code)
    
    assert result["status"] == "error"
    assert result["error"]["type"] == "EXECUTION_ERROR"
    assert "division by zero" in result["error"]["message"]

@pytest.mark.asyncio
async def test_run_python_timeout_error(test_db, monkeypatch):
    """
    Проверяет, что выполнение кода прерывается по таймауту.
    """
    # Уменьшаем таймаут для теста
    monkeypatch.setattr("agent.services.query_executor.SANDBOX_TIMEOUT_SECONDS", 2)
    
    query_executor = QueryExecutor()
    python_code = "import time; time.sleep(5)" # Спим дольше таймаута
    result = await query_executor.run_python(python_code)
    
    assert result["status"] == "error"
    assert result["error"]["type"] == "TIMEOUT_ERROR"
    assert "превысило лимит времени" in result["error"]["message"]
