# agent/services/data_profiler.py
import asyncio
from typing import Dict, Any, List
# --- ИЗМЕНЕНИЕ: Импортируем 'types' из sqlalchemy ---
from sqlalchemy import create_engine, text, inspect, types as sqltypes
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd
from loguru import logger

from agent.config import settings
from agent.schemas import TableProfile, ColumnProfile, HistogramBin, TopValue

# Количество бинов для гистограммы и топ-N значений
HISTOGRAM_BINS = 10
TOP_N_VALUES = 10
DISTINCT_EXAMPLES_COUNT = 15 # Будем собирать 15 примеров

class DataProfiler:
    def __init__(self):
        try:
            sync_db_url = str(settings.DATABASE_URL).replace("+psycopg", "")
            self.engine = create_engine(sync_db_url, pool_pre_ping=True)
            self.inspector = inspect(self.engine)
            logger.info("Data Profiler инициализирован.")
        except Exception as e:
            logger.error(f"Ошибка инициализации Data Profiler: {e}")
            raise

    async def profile_table(self, table_name: str) -> TableProfile:
        """Создает полный профиль для указанной таблицы."""
        # Проверяем, существует ли таблица
        if not self.inspector.has_table(table_name):
            raise ValueError(f"Таблица '{table_name}' не найдена в базе данных.")

        columns = self.inspector.get_columns(table_name)
        column_profiles = []

        for column in columns:
            col_name = column['name']
            col_type = column['type']
            
            # Асинхронно запускаем сбор статистики для каждого столбца
            profile = await self._profile_column(table_name, col_name, col_type)
            column_profiles.append(profile)
            
        return TableProfile(table_name=table_name, columns=column_profiles)

    async def _profile_column(self, table_name: str, column_name: str, col_type) -> ColumnProfile:
        """Профилирует один столбец, собирая статистику, топ-N и примеры."""
        
        def db_calls():
            with self.engine.connect() as connection:
                # 1. Считаем NULL'ы
                null_count_query = text(f'SELECT COUNT(*) FROM "{table_name}" WHERE "{column_name}" IS NULL')
                null_count = connection.execute(null_count_query).scalar_one()

                histogram = None
                top_values = None
                distinct_examples = None

                # --- ИЗМЕНЕНИЕ: Исправлена проверка на числовой тип ---
                # Теперь мы используем корректную проверку через `isinstance` с базовым
                # числовым типом из SQLAlchemy.
                if isinstance(col_type, sqltypes.Numeric):
                # --------------------------------------------------------
                    min_max_query = text(f'SELECT MIN("{column_name}"), MAX("{column_name}") FROM "{table_name}"')
                    min_val, max_val = connection.execute(min_max_query).one()
                    
                    if min_val is not None and max_val is not None and min_val < max_val:
                        hist_query = text(f"""
                            SELECT
                                MIN("{column_name}") as bucket_start,
                                MAX("{column_name}") as bucket_end,
                                COUNT(*) as count
                            FROM (
                                SELECT "{column_name}", NTILE({HISTOGRAM_BINS}) OVER (ORDER BY "{column_name}") as bucket
                                FROM "{table_name}" WHERE "{column_name}" IS NOT NULL
                            ) as t
                            GROUP BY bucket
                            ORDER BY bucket;
                        """)
                        hist_result = connection.execute(hist_query).fetchall()
                        histogram = [HistogramBin(bucket_start=r[0], bucket_end=r[1], count=r[2]) for r in hist_result]

                # 3. Логика для текстовых/категориальных/других типов
                else:
                    # 3a. Собираем топ-N самых частых значений
                    top_values_query = text(f"""
                        SELECT "{column_name}", COUNT(*) as count
                        FROM "{table_name}" WHERE "{column_name}" IS NOT NULL
                        GROUP BY "{column_name}" ORDER BY count DESC LIMIT {TOP_N_VALUES};
                    """)
                    top_values_result = connection.execute(top_values_query).fetchall()
                    top_values = [TopValue(value=r[0], count=r[1]) for r in top_values_result]

                    # 3b. Собираем примеры уникальных значений
                    examples_query = text(f"""
                        SELECT DISTINCT "{column_name}"
                        FROM "{table_name}"
                        WHERE "{column_name}" IS NOT NULL
                        LIMIT {DISTINCT_EXAMPLES_COUNT};
                    """)
                    examples_result = connection.execute(examples_query).fetchall()
                    distinct_examples = [r[0] for r in examples_result]
                
                return null_count, histogram, top_values, distinct_examples

        # Получаем все результаты из фонового потока
        null_count, histogram, top_values, distinct_examples = await asyncio.to_thread(db_calls)

        # Собираем финальный объект Pydantic
        return ColumnProfile(
            name=column_name, 
            null_count=null_count, 
            histogram=histogram, 
            top_values=top_values,
            distinct_examples=distinct_examples
        )

# Создаем синглтон
data_profiler = DataProfiler()