import logging
from typing import Dict, Any, List

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Inspector

from agent.config import settings

logger = logging.getLogger(__name__)

class DatabaseInspector:
    """
    Сервис для интроспекции (анализа) структуры подключенной базы данных.
    """
    def __init__(self):
        # Создаем синхронный движок SQLAlchemy, так как интроспекция
        # не всегда хорошо поддерживается асинхронными драйверами и
        # является быстрой операцией, не требующей async.
        try:
            # Преобразуем асинхронный URL в синхронный, если нужно
            sync_db_url = str(settings.DATABASE_URL).replace("+asyncpg", "").replace("+aiosqlite", "").replace("+psycopg", "")
            self.engine = create_engine(sync_db_url, pool_pre_ping=True)
            self.inspector: Inspector = inspect(self.engine)
            logger.info("Инспектор базы данных успешно инициализирован.")
        except Exception as e:
            logger.error(f"Ошибка при инициализации инспектора БД: {e}", exc_info=True)
            raise

    async def get_schema(self) -> Dict[str, Any]:
        """
        Собирает и возвращает детальную схему базы данных.
        """
        logger.info("Начало сбора схемы базы данных...")
        try:
            schema_names = self.inspector.get_schema_names()
            
            # Мы будем собирать информацию из публичной схемы по умолчанию,
            # но можно расширить для поддержки нескольких схем.
            target_schema = "public" if "public" in schema_names else None
            
            table_names = self.inspector.get_table_names(schema=target_schema)
            
            tables_info: List[Dict[str, Any]] = []
            for table_name in table_names:
                columns_info: List[Dict[str, Any]] = []
                columns = self.inspector.get_columns(table_name, schema=target_schema)
                
                pk_constraint = self.inspector.get_pk_constraint(table_name, schema=target_schema)
                primary_keys = pk_constraint.get('constrained_columns', []) if pk_constraint else []

                for column in columns:
                    columns_info.append({
                        "name": column["name"],
                        "type": str(column["type"]),
                        "nullable": column["nullable"],
                        "default": column["default"],
                        "is_primary_key": column["name"] in primary_keys
                    })
                
                tables_info.append({
                    "name": table_name,
                    "columns": columns_info
                })

            full_schema = {
                "dialect": self.engine.dialect.name,
                "schema": {
                    "tables": tables_info
                }
            }
            logger.info(f"Сбор схемы завершен. Найдено таблиц: {len(tables_info)}")
            return full_schema

        except Exception as e:
            logger.error(f"Ошибка при получении схемы БД: {e}", exc_info=True)
            raise RuntimeError(f"Не удалось получить схему базы данных: {e}")

# Создаем единственный экземпляр инспектора
db_inspector = DatabaseInspector()