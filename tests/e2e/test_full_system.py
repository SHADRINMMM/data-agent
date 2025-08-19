# tests/e2e/test_full_system.py
import pytest
import httpx
import os
import pandas as pd

# URL агента внутри сети Docker
AGENT_URL = "http://agent:8080"
# Токен должен совпадать с AGENT_SECRET_TOKEN в .env.test
TEST_TOKEN = os.getenv("AGENT_SECRET_TOKEN", "test-token-12345")

@pytest.mark.asyncio
async def test_health_check():
    """Проверяет, что агент жив и отвечает на /health."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{AGENT_URL}/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "db_dialect": "postgresql"}

@pytest.mark.asyncio
async def test_get_schema_unauthorized():
    """Проверяет, что эндпоинт /schema защищен."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{AGENT_URL}/schema")
        assert response.status_code == 401 # Или 403 в зависимости от реализации

@pytest.mark.asyncio
async def test_get_schema_authorized():
    """Проверяет, что с верным токеном можно получить схему."""
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    async with httpx.AsyncClient() as client:
        # Сначала создадим таблицу через SQL-запрос
        sql_payload = {
            "language": "sql",
            "code": "CREATE TABLE test_e2e (id INT);"
        }
        # В нашей реализации CREATE запрещен, это ожидаемо!
        # Здесь мы можем проверить, что небезопасный запрос отклоняется
        response_create = await client.post(f"{AGENT_URL}/execute", json=sql_payload, headers=headers)
        assert response_create.status_code == 403 # PermissionError

        # Теперь проверим схему. Пока таблиц быть не должно.
        response_schema = await client.get(f"{AGENT_URL}/schema", headers=headers)
        assert response_schema.status_code == 200
        schema = response_schema.json()
        assert schema["dialect"] == "postgresql"
        # Проверяем, что в списке таблиц нет нашей `test_e2e`
        assert "test_e2e" not in [t["name"] for t in schema["schema"]["tables"]]

@pytest.mark.asyncio
async def test_sql_execution_flow():
    """Проверяет полный цикл выполнения безопасного SQL-запроса."""
    # Примечание: для этого теста нужно, чтобы в БД были данные.
    # В идеале, их нужно создавать не через API агента (т.к. INSERT запрещен),
    # а через отдельный скрипт, который наполняет test-db.
    # Но для примера, давайте проверим простой SELECT.
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    payload = {
        "language": "sql",
        "code": "SELECT 1 as number;"
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{AGENT_URL}/execute", json=payload, headers=headers)
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "success"
        # assert result["result"]["columns"] == ["number"]
        # assert result["result"]["rows"] == [[1]]

@pytest.mark.asyncio
async def test_execute_on_data_flow():
    """
    Проверяет полный E2E цикл для эндпоинта /execute-on-data.
    """
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    
    # 1. Готовим входные данные
    df_input = pd.DataFrame({
        "region": ["North", "South", "North", "South"],
        "sales": [100, 150, 80, 200]
    })
    input_data_json = df_input.to_dict(orient='split')

    # 2. Готовим код для выполнения
    python_code = """
# Входные данные лежат в словаре input_data
sales_df = input_data['sales_data']
# Группируем и считаем сумму
result_df = sales_df.groupby('region')['sales'].sum().reset_index()
"""

    # 3. Формируем тело запроса
    payload = {
        "code": python_code,
        "input_data": {
            "sales_data": input_data_json
        }
    }

    # 4. Отправляем запрос
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(f"{AGENT_URL}/execute-on-data", json=payload, headers=headers)

    # 5. Проверяем ответ
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["status"] == "success"

    # 6. Проверяем корректность вычислений
    result_data = response_json["result"]
    df_output = pd.DataFrame(result_data['data'], columns=result_data['columns'])
    
    # Ожидаемый результат
    # North: 100 + 80 = 180
    # South: 150 + 200 = 350
    assert len(df_output) == 2
    north_sales = df_output[df_output['region'] == 'North']['sales'].iloc[0]
    south_sales = df_output[df_output['region'] == 'South']['sales'].iloc[0]
    assert north_sales == 180
    assert south_sales == 350

