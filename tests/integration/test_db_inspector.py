# tests/integration/test_db_inspector.py
import pytest
from agent.services.db_inspector import DatabaseInspector
from agent.config import AgentSettings

@pytest.mark.asyncio
async def test_get_schema_integration(test_db, monkeypatch):
    """
    Интеграционный тест для DatabaseInspector.
    Использует фикстуру test_db для получения готовой БД.
    Вызывает get_schema() и проверяет результат.
    """
    # Фикстура test_db уже настроила БД.
    # Мы используем реальные настройки из .env.test, так как агент и БД
    # находятся в одной Docker-сети.
    
    db_inspector = DatabaseInspector()
    
    # Получаем схему
    schema_result = await db_inspector.get_schema()
    
    # --- Проверки ---
    assert schema_result["dialect"] == "postgresql"
    
    tables = schema_result["schema"]["tables"]
    table_names = {t["name"] for t in tables}
    
    # Проверяем, что наши таблицы 'users' и 'products' на месте
    assert "users" in table_names
    assert "products" in table_names
    
    # Проверяем структуру таблицы 'users'
    users_table = next(t for t in tables if t["name"] == "users")
    users_columns = {c["name"]: c for c in users_table["columns"]}
    assert "id" in users_columns
    assert users_columns["id"]["is_primary_key"] is True
    assert "username" in users_columns
    assert users_columns["username"]["type"] == "VARCHAR(50)"
    assert users_columns["username"]["nullable"] is False
    
    # Проверяем структуру таблицы 'products'
    products_table = next(t for t in tables if t["name"] == "products")
    products_columns = {c["name"]: c for c in products_table["columns"]}
    assert "price" in products_columns
    assert "NUMERIC(10, 2)" in products_columns["price"]["type"]
    assert "user_id" in products_columns
