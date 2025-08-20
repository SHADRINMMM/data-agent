from typing import Annotated, Dict, Any

from fastapi import APIRouter, Depends, Security, HTTPException, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from loguru import logger

from agent.config import settings
# Импортируем наши реальные сервисы
from agent.services.db_inspector import db_inspector
from agent.services.query_executor import query_executor
from agent.services.data_profiler import data_profiler # <-- НОВЫЙ
from agent.schemas import EnrichedExecutionResult, TableProfile # <-- ОБНОВИТЬ

router = APIRouter()

# --- Pydantic Схемы ---
class ExecuteCodeRequest(BaseModel):
    language: str = Field(..., description="Язык программирования ('python' или 'sql').")
    code: str = Field(..., description="Код для выполнения.")

class ExecuteOnDataRequest(BaseModel):
    code: str = Field(..., description="Python-код для выполнения.")
    # 'input_data' - это словарь, где ключ - имя переменной,
    # а значение - JSON-представление DataFrame'а (orient='split'), 
    # с которым будет работать pandas.
    cache_keys: Optional[Dict[str, str]] = Field(None, description="Словарь, где ключ - имя переменной, а значение - ключ кеша для загрузки DataFrame.")
    input_data: Dict[str, Any] = Field({}, description="Словарь с входными данными в формате JSON (orient='split').")


# --- Зависимость для проверки секретного токена ---

auth_scheme = APIKeyHeader(name="Authorization", auto_error=False)

async def verify_token(token: Annotated[str, Security(auth_scheme)]):
    """
    Проверяет, что предоставленный токен соответствует токену из .env.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется токен авторизации."
        )
    
    try:
        scheme, _, credentials = token.partition(" ")
        if not scheme or scheme.lower() != "bearer" or not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный формат токена. Ожидается 'Bearer <token>'."
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный формат токена."
        )

    if credentials != settings.AGENT_SECRET_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Неверный или недействительный токен."
        )

# --- Эндпоинты API Агента ---

@router.get("/health", summary="Проверка работоспособности агента", tags=["Agent"])
async def health_check():
    """
    Простой эндпоинт для проверки, что агент жив и отвечает на запросы.
    """
    return {"status": "ok", "db_dialect": settings.DB_DIALECT}

@router.get("/schema", summary="Получить схему базы данных", dependencies=[Depends(verify_token)], tags=["Agent"])
async def get_database_schema() -> Dict[str, Any]:
    """
    Возвращает структуру подключенной базы данных.
    Защищено токеном.
    """
    try:
        schema = await db_inspector.get_schema()
        return schema
    except Exception as e:
        # Если сервис инспекции выдаст ошибку, мы ее перехватим и вернем 500
        raise HTTPException(status_code=500, detail=f"Ошибка получения схемы: {e}")

@router.get(
    "/schema/{table_name}/profile",
    response_model=TableProfile,
    summary="Получить детальный профиль таблицы",
    dependencies=[Depends(verify_token)],
    tags=["Agent"]
)
async def get_table_profile(table_name: str):
    """
    Возвращает детальную статистику для указанной таблицы, включая
    распределение значений и самые частые значения для каждого столбца.
    """
    try:
        profile = await data_profiler.profile_table(table_name)
        return profile
    except ValueError as e: # Если таблица не найдена
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при профилировании таблицы '{table_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка при профилировании таблицы: {e}")

@router.post("/execute", summary="Выполнить код", dependencies=[Depends(verify_token)], tags=["Agent"])
async def execute_query(payload: ExecuteCodeRequest) -> EnrichedExecutionResult:
    """
    Выполняет SQL-запрос или Python-код.
    Защищено токеном.
    """
    result = await query_executor.run(language=payload.language, code=payload.code)
    
    if result.get("status") == "error":
        error_details = result.get("error", {})
        error_type = error_details.get("type")

        if error_type == "PERMISSION_ERROR":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_details
            )
        else:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_details
            )
            
    return result

@router.post(
    "/execute-on-data", 
    summary="Выполнить Python-код над переданными данными", 
    dependencies=[Depends(verify_token)], 
    tags=["Agent"],
)
async def execute_on_data(payload: ExecuteOnDataRequest) -> EnrichedExecutionResult:
    """
    Выполняет Python-код в песочнице, передавая ему на вход предоставленные данные.

    - **code**: Python-код. Должен создавать переменную `result_df` типа pandas.DataFrame.
    - **input_data**: Словарь, где каждый ключ - это имя DataFrame, а значение - 
      его JSON-представление (`orient='split'`). Внутри кода эти данные будут 
      доступны через словарь `input_data`.
    """
    result = await query_executor.run_python_on_data(
        python_code=payload.code,
        input_data=payload.input_data,
        cache_keys=payload.cache_keys  # <-- ДОБАВЛЕНА ЭТА СТРОКА
    )
    
    if result.get("status") == "error":
        error_details = result.get("error", {})
        error_type = error_details.get("type")

        if error_type == "PERMISSION_ERROR":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_details)
        else: # Для TIMEOUT_ERROR, EXECUTION_ERROR, SERIALIZATION_ERROR и др.
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_details)
            
    return result
