# agent/services/query_executor.py

import asyncio
import json
import time
from typing import Dict, Any, Literal, Optional
import docker
from docker.errors import NotFound, ContainerError
from loguru import logger
import pandas as pd
import numpy as np
import math
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from agent.config import settings
from agent.services.sql_safety_check import is_sql_safe
# Импортируем наши новые модели
from agent.schemas import EnrichedExecutionResult, ExecutionMetadata, ExecutionData, ColumnMetadata, ColumnStats

# Docker settings
from agent.config import settings
from agent.services.sql_safety_check import is_sql_safe
from agent.services.data_cache import AgentDataCache
# Импортируем наши новые модели
from agent.schemas import EnrichedExecutionResult, ExecutionMetadata, ExecutionData, ColumnMetadata, ColumnStats

# Docker settings
DOCKER_CLIENT = docker.from_env()
SANDBOX_IMAGE_NAME = "causabi-python-sandbox:latest"
EXECUTION_TIMEOUT_SECONDS = 100

# Cache instance
agent_cache = AgentDataCache()

SANDBOX_IMAGE_NAME = "causabi-python-sandbox:latest"
EXECUTION_TIMEOUT_SECONDS = 100

# --- ДОБАВЬТЕ ЭТУ ВСПОМОГАТЕЛЬНУЮ ФУНКЦИЮ ПЕРЕД _build_enriched_response_from_df ---
def _sanitize_float(value: Any) -> Optional[float]:
    """
    Преобразует float-значения, несовместимые с JSON (NaN, inf, -inf), в None.
    Возвращает обычные числа без изменений.
    """
    if value is None or not isinstance(value, (float, np.floating)):
        return value
    if not math.isfinite(value):
        return None  # Заменяем NaN, inf, -inf на None
    return float(value)
# ----------------------------------------------------------------------------------


def _build_enriched_response_from_df(df: pd.DataFrame, exec_time_ms: float) -> dict:
    """
    Вспомогательная функция для создания обогащенного ответа из DataFrame.
    """
    column_metadata_list: list[ColumnMetadata] = []
    
    # Эта переменная должна быть инициализирована в любом случае.
    metadata: Optional[ExecutionMetadata] = None

    for col_name in df.columns:
        col_series = df[col_name]
        col_type = str(col_series.dtype)
        stats = None

        if pd.api.types.is_numeric_dtype(col_series.dtype):
            desc = col_series.describe()
            # --- ИЗМЕНЕНИЕ: Применяем нашу "очищающую" функцию ко всем значениям ---
            stats = ColumnStats(
                min=_sanitize_float(desc.get('min')),
                max=_sanitize_float(desc.get('max')),
                mean=_sanitize_float(desc.get('mean')),
                std_dev=_sanitize_float(desc.get('std')),
                unique_count=col_series.nunique()
            )
            # ---------------------------------------------------------------------
        elif pd.api.types.is_datetime64_any_dtype(col_series.dtype):
             stats = ColumnStats(
                min=str(col_series.min()) if not col_series.empty and pd.notna(col_series.min()) else None,
                max=str(col_series.max()) if not col_series.empty and pd.notna(col_series.max()) else None,
                unique_count=col_series.nunique()
            )
        else:
             stats = ColumnStats(unique_count=col_series.nunique())

        column_metadata_list.append(ColumnMetadata(name=col_name, type=col_type, stats=stats))

    metadata = ExecutionMetadata(
        execution_time_ms=exec_time_ms,
        row_count=len(df),
        result_schema=column_metadata_list
    )

    data = ExecutionData(
        columns=df.columns.tolist(),
        rows=df.where(pd.notna(df), None).values.tolist()
    )

    result = EnrichedExecutionResult(metadata=metadata, data=data)
    return result.model_dump()


class QueryExecutor:
    """
    Service for executing SQL queries and Python code.
    """
    def __init__(self):
        try:
            sync_db_url = str(settings.DATABASE_URL).replace("+psycopg", "")
            self.engine = create_engine(sync_db_url, pool_pre_ping=True)
            self.docker_client = docker.from_env()
            self.docker_client.ping()
            self.docker_network = self._get_docker_network()
            logger.info("Query Executor and Docker client initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing QueryExecutor: {e}", exc_info=True)
            self.engine = None
            self.docker_client = None
            raise

    def _get_docker_network(self) -> str:
        """Determines the Docker network for the sandbox container."""
        if settings.DOCKER_NETWORK:
            return settings.DOCKER_NETWORK
        try:
            container_id = __import__("socket").gethostname()
            container = self.docker_client.containers.get(container_id)
            network_name = list(container.attrs['NetworkSettings']['Networks'].keys())[0]
            logger.info(f"Automatically detected Docker network: {network_name}")
            return network_name
        except Exception:
            logger.warning("Could not auto-detect Docker network. Falling back to 'host'.")
            return "host"

    async def run(self, language: Literal["sql", "python"], code: str) -> Dict[str, Any]:
        """Dispatches the execution to the correct method based on language."""
        if language == "sql":
            return await self.run_sql(code)
        elif language == "python":
            return await self.run_python(code)
        else:
            logger.warning(f"Attempt to execute code in unsupported language: {language}")
            return {"status": "error", "error": {"type": "UNSUPPORTED_LANGUAGE", "message": "Only 'sql' and 'python' are supported."}}

    async def run_sql(self, sql_code: str) -> Dict[str, Any]:
        """
        Executes a SQL query, collects metadata, and returns an enriched result.
        """
        is_safe, error_message = is_sql_safe(sql_code, settings.DB_DIALECT)
        if not is_safe:
            return {"status": "error", "error": {"type": "PERMISSION_ERROR", "message": error_message}}

        if not self.engine:
             return {"status": "error", "error": {"type": "CONFIGURATION_ERROR", "message": "Database engine not initialized."}}

        start_time = time.monotonic()
        try:
            def db_call() -> pd.DataFrame:
                with self.engine.connect() as connection:
                    result_proxy = connection.execute(text(sql_code))
                    if not result_proxy.returns_rows:
                        return pd.DataFrame()
                    return pd.DataFrame(result_proxy.fetchall(), columns=result_proxy.keys())

            df = await asyncio.to_thread(db_call)
            exec_time_ms = (time.monotonic() - start_time) * 1000

            logger.info(f"SQL query executed successfully in {exec_time_ms:.2f} ms. Rows: {len(df)}")
            
            # --- КЕШИРОВАНИЕ РЕЗУЛЬТАТА ---
            enriched_response = _build_enriched_response_from_df(df, exec_time_ms)
            try:
                cache_key = agent_cache.save(df)
                enriched_response["cache_key"] = cache_key
                logger.info(f"SQL result cached successfully. Key: {cache_key}")
            except Exception as e:
                logger.error(f"Failed to cache SQL result: {e}")
                # Не страшно, просто вернем результат без ключа

            return enriched_response

        except SQLAlchemyError as e:
            return {"status": "error", "error": {"type": "DATABASE_ERROR", "message": str(e).strip()}}
        except Exception as e:
            return {"status": "error", "error": {"type": "UNEXPECTED_ERROR", "message": str(e).strip()}}

    async def run_python(self, python_code: str) -> Dict[str, Any]:
        """Prepares the environment for Python code execution that accesses the DB."""
        db_url = str(settings.DATABASE_URL).replace('+psycopg', '')
        environment = {
            "PYTHON_CODE_TO_EXECUTE": python_code,
            "DATABASE_URL": db_url,
        }
        return await self._run_python_in_sandbox(environment)

    async def run_python_on_data(self, python_code: str, input_data: Dict[str, Any], cache_keys: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Выполняет Python-код. Данные для переменных берутся из кеша по `cache_keys`.
        Если ключ не найден, используются данные из `input_data` (считаются сэмплами).
        """
        final_input_dataframes = {}

        # 1. Загрузка данных из кеша (приоритетный способ)
        if cache_keys:
            for var_name, key in cache_keys.items():
                try:
                    final_input_dataframes[var_name] = agent_cache.load(key)
                except FileNotFoundError:
                    return {"status": "error", "error": {"type": "CACHE_MISS_ERROR", "message": f"Ключ кеша '{key}' для переменной '{var_name}' не найден. Возможно, кеш агента был очищен или время жизни истекло."}}
                except Exception as e:
                    return {"status": "error", "error": {"type": "CACHE_LOAD_ERROR", "message": f"Ошибка загрузки данных из кеша для ключа '{key}': {e}"}}

        # 2. Загрузка данных из сэмплов (fallback)
        if input_data:
            for var_name, data_json in input_data.items():
                if var_name not in final_input_dataframes:
                    logger.warning(f"Ключ кеша для '{var_name}' не предоставлен, используется сэмпл данных из запроса.")
                    try:
                        # pandas требует, чтобы данные были строкой json, а не python dict
                        final_input_dataframes[var_name] = pd.read_json(json.dumps(data_json), orient='split')
                    except Exception as e:
                        return {"status": "error", "error": {"type": "DESERIALIZATION_ERROR", "message": f"Не удалось десериализовать сэмпл данных для '{var_name}': {e}"}}

        # 3. Сериализация ПОЛНЫХ данных для передачи в песочницу
        try:
            serialized_full_data = {
                var_name: json.loads(df.to_json(orient="split", date_format="iso", index=False))
                for var_name, df in final_input_dataframes.items()
            }
            input_data_json_str = json.dumps(serialized_full_data)
        except TypeError as e:
            return {"status": "error", "error": {"type": "SERIALIZATION_ERROR", "message": f"Не удалось сериализовать итоговые данные для песочницы: {e}"}}

        db_url = str(settings.DATABASE_URL).replace('+psycopg', '')
        environment = {
            "PYTHON_CODE_TO_EXECUTE": python_code,
            "INPUT_DATA_JSON": input_data_json_str,
            "DATABASE_URL": db_url
        }
        
        # --- НОВАЯ ЛОГИКА ВЫПОЛНЕНИЯ И КЕШИРОВАНИЯ РЕЗУЛЬТАТА ---
        result_from_sandbox = await self._run_python_in_sandbox(environment)

        if result_from_sandbox.get("status") != "error":
            # После успешного выполнения кода в песочнице, его результат тоже нужно закешировать!
            try:
                result_data = result_from_sandbox.get("data", {})
                result_df = pd.DataFrame(data=result_data.get("rows", []), columns=result_data.get("columns", []))
                
                new_cache_key = agent_cache.save(result_df)
                result_from_sandbox["cache_key"] = new_cache_key # Добавляем новый ключ в ответ
            except Exception as e:
                logger.error(f"Не удалось закешировать результат Python-шага: {e}")
                # Не страшно, просто вернем результат без ключа
        
        return result_from_sandbox

    async def _run_python_in_sandbox(self, environment: Dict[str, Any]) -> Dict[str, Any]:
        """Executes Python code in Docker, gets enriched result, adds total exec time."""
        container = None
        start_time = time.monotonic()
        try:
            container = self.docker_client.containers.run(
                SANDBOX_IMAGE_NAME, detach=True, environment=environment,
                network=self.docker_network, mem_limit="256m", cpu_period=100000, cpu_quota=50000
            )
            result = await asyncio.to_thread(container.wait, timeout=EXECUTION_TIMEOUT_SECONDS)
            exec_time_ms = (time.monotonic() - start_time) * 1000

            exit_code = result.get("StatusCode", -1)
            stdout = container.logs(stdout=True, stderr=False).decode('utf-8').strip()
            stderr = container.logs(stdout=False, stderr=True).decode('utf-8').strip()

            if exit_code == 0:
                try:
                    # Песочница уже возвращает обогащенную структуру
                    enriched_result = json.loads(stdout)
                    # Мы просто добавляем/перезаписываем время выполнения, измеренное "снаружи"
                    enriched_result['metadata']['execution_time_ms'] = exec_time_ms
                    logger.success(f"Python code executed successfully in sandbox in {exec_time_ms:.2f} ms.")
                    return enriched_result
                except json.JSONDecodeError:
                    return {"status": "error", "error": {"type": "SERIALIZATION_ERROR", "message": "Failed to deserialize result from sandbox."}}
            else:
                return {"status": "error", "error": {"type": "EXECUTION_ERROR", "message": stderr}}
        
        except asyncio.TimeoutError:
            exec_time_ms = (time.monotonic() - start_time) * 1000
            if container:
                try: container.stop(timeout=5)
                except: pass
            return {"status": "error", "error": {"type": "TIMEOUT_ERROR", "message": f"Execution took longer than {exec_time_ms/1000:.1f}s (limit: {EXECUTION_TIMEOUT_SECONDS}s)."}}
        except ContainerError as e:
            return {"status": "error", "error": {"type": "EXECUTION_ERROR", "message": str(e)}}
        except NotFound:
            return {"status": "error", "error": {"type": "CONFIGURATION_ERROR", "message": f"Docker image '{SANDBOX_IMAGE_NAME}' not found."}}
        except Exception as e:
            return {"status": "error", "error": {"type": "UNKNOWN_ERROR", "message": str(e)}}
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception as e:
                    logger.warning(f"Failed to remove container {container.id}: {e}")

query_executor = QueryExecutor()
