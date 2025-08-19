# tests/unit/test_sql_safety.py
import pytest
from agent.services.query_executor import QueryExecutor

# Создаем экземпляр QueryExecutor для доступа к методу _is_unsafe_sql
try:
    executor = QueryExecutor()
except Exception:
    from unittest.mock import MagicMock
    QueryExecutor.__init__ = MagicMock(return_value=None)
    executor = QueryExecutor()


# --- Тесты для безопасных запросов (ожидаем False) ---

@pytest.mark.parametrize("safe_query", [
    "SELECT * FROM users",
    "select name, email from customers where id = 1",
    "WITH regional_sales AS (SELECT region, SUM(amount) AS total_sales FROM orders GROUP BY region) SELECT region, total_sales FROM regional_sales WHERE total_sales > 1000",
    "SELECT a, b FROM table1 UNION ALL SELECT c, d FROM table2",
    '''  SELECT
	col1
  FROM
	 my_table ''',
    "SELECT * FROM products -- this is a comment",
    "/* Multi-line comment */ SELECT id FROM logs",
    "SELECT 1",
    "SELECT 1;",
])
def test_is_unsafe_sql_with_safe_queries(safe_query):
    """Проверяет, что различные безопасные SELECT-запросы проходят проверку."""
    assert executor._is_unsafe_sql(safe_query) is False, f"Query failed: {safe_query}"


# --- Тесты для опасных запросов (ожидаем True) ---

@pytest.mark.parametrize("unsafe_query", [
    "DROP TABLE users",
    "DELETE FROM products WHERE id = 1",
    "INSERT INTO users (name) VALUES ('test')",
    "UPDATE customers SET name = 'new_name' WHERE id = 1",
    "TRUNCATE TABLE logs",
    "ALTER TABLE products ADD COLUMN new_col INT",
    "CREATE TABLE new_table (id INT)",
    "GRANT SELECT ON users TO public",
    "REVOKE ALL ON secrets FROM user",
    "CALL some_procedure()",
    "SELECT * FROM users; DROP TABLE users", # Множественные команды
    "SELECT * FROM users; -- DROP TABLE users", # Множественные команды с комментарием
    "UPDATE users SET name = 'new_name' WHERE id = 1",
    "SELECT 1; UPDATE users SET name='hacker'"
])
def test_is_unsafe_sql_with_unsafe_queries(unsafe_query):
    """Проверяет, что опасные SQL-команды блокируются."""
    assert executor._is_unsafe_sql(unsafe_query) is True, f"Query failed: {unsafe_query}"

@pytest.mark.parametrize("tricky_query", [
    "SELECT * FROM users_update", # Похоже на 'update', но безопасное имя
    "SELECT information_schema.tables", # Безопасный запрос к системной таблице
])
def test_is_unsafe_sql_with_tricky_safe_queries(tricky_query):
    """Проверяет, что запросы, содержащие 'опасные' слова как часть имен, не блокируются."""
    assert executor._is_unsafe_sql(tricky_query) is False, f"Query failed: {tricky_query}"

@pytest.mark.parametrize("tricky_unsafe_query", [
    "SELECT * FROM users\n--comment\n;UPDATE customers SET name='new'", # Обновление после комментария
    "SELECT 1; /* comment */ DELETE FROM products", # Удаление после многострочного комментария
    "SELECT col1, (SELECT count(*) from users u where u.id=p.id and 1=1) from products p; drop table secrets" # Вложенный запрос и атака
])
def test_is_unsafe_sql_with_tricky_unsafe_queries(tricky_unsafe_query):
    """Проверяет, что опасные команды не проходят даже с комментариями или вложенными запросами."""
    assert executor._is_unsafe_sql(tricky_unsafe_query) is True, f"Query failed: {tricky_unsafe_query}"

def test_is_unsafe_sql_case_insensitivity():
    """Проверяет, что проверка нечувствительна к регистру."""
    assert executor._is_unsafe_sql("sElEcT * fRoM uSeRs") is False
    assert executor._is_unsafe_sql("DrOp TaBlE users") is True
    assert executor._is_unsafe_sql("wItH sales AS (SELECT * FROM orders) sElEcT * fRoM sales") is False

def test_is_unsafe_sql_with_comments_hiding_danger():
    """Проверяет, что опасные слова внутри комментариев игнорируются, но реальные команды - нет."""
    # Опасное слово внутри комментария - должно быть безопасно
    safe_query = "SELECT * FROM users -- This is a comment about DROP TABLE"
    assert executor._is_unsafe_sql(safe_query) is False

    # Опасная команда после комментария - должно быть опасно
    unsafe_query = "SELECT * FROM users; /* comment */ DROP TABLE products"
    assert executor._is_unsafe_sql(unsafe_query) is True