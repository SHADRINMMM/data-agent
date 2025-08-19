# tests/integration/conftest.py
import pytest
import psycopg2
import time
import logging
import os
from agent.config import AgentSettings

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture(scope="session", autouse=True)
def wait_for_db():
    """
    Фикстура (session-scoped), которая ждет, пока база данных,
    запущенная через docker-compose.test.yml, станет доступной.
    """
    settings = AgentSettings()
    # SQLAlchemy URL -> DSN for psycopg2
    conn_string = settings.DATABASE_URL.replace('+psycopg', '').replace('postgresql://', 'postgresql://')
    
    retries = 15
    delay = 3
    for i in range(retries):
        try:
            conn = psycopg2.connect(conn_string)
            conn.close()
            logger.info("✅ База данных готова к приему подключений.")
            return
        except psycopg2.OperationalError:
            logger.info(f"⏳ Ожидание БД... (попытка {i+1}/{retries})")
            time.sleep(delay)
    pytest.fail("Не удалось подключиться к тестовой БД после нескольких попыток.")

@pytest.fixture(scope="session")
def db_connection(wait_for_db):
    """
    Создает одно соединение с БД на всю сессию тестов.
    """
    settings = AgentSettings()
    conn_string = settings.DATABASE_URL.replace('+psycopg', '')
    try:
        conn = psycopg2.connect(conn_string)
        yield conn
        conn.close()
        logger.info("Соединение с БД (session) закрыто.")
    except psycopg2.OperationalError as e:
        pytest.fail(f"Не удалось создать соединение с БД на всю сессию: {e}")

@pytest.fixture(scope="function")
def test_db(db_connection):
    """
    Фикстура (function-scoped), которая перед каждым тестом:
    1. Выполняет setup_test_db.sql для создания и наполнения таблиц.
    После каждого теста:
    1. Удаляет созданные таблицы для обеспечения изоляции тестов.
    """
    # Определяем путь к файлу setup_test_db.sql
    # __file__ -> tests/integration/conftest.py
    # os.path.dirname(__file__) -> tests/integration
    # os.path.join(..., '..') -> tests
    sql_file_path = os.path.join(os.path.dirname(__file__), '..', 'setup_test_db.sql')

    with open(sql_file_path, 'r') as f:
        sql_script = f.read()
    
    with db_connection.cursor() as cur:
        # Убедимся, что таблицы не существуют перед созданием
        cur.execute("DROP TABLE IF EXISTS products, users CASCADE;")
        db_connection.commit()

        # Выполняем скрипт
        cur.execute(sql_script)
        db_connection.commit()
        logger.info("Тестовая схема создана из файла.")

    yield

    with db_connection.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS products, users CASCADE;")
        db_connection.commit()
        logger.info("Тестовые таблицы удалены.")