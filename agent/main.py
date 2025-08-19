import logging
import asyncio
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agent.config import settings
from agent.api import router as api_router

# Настройка логирования для Агента
logging.basicConfig(level=logging.INFO, format='%(asctime)s - AGENT - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Логика регистрации агента в Core Logic ---

async def register_agent():
    """
    Отправляет ping-запрос в Core Logic для регистрации.
    Пытается сделать это несколько раз с задержкой в случае неудачи.
    """
    registration_url = f"{settings.CORE_LOGIC_URL.rstrip('/')}/api/v1/agents/register"
    payload = {
        "agent_secret_token": settings.AGENT_SECRET_TOKEN,
        "agent_public_url": settings.AGENT_PUBLIC_URL
    }
    headers = {"Content-Type": "application/json"}
    
    max_retries = 5
    retry_delay = 5  # секунд

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"Попытка регистрации агента в Core Logic (попытка {attempt + 1}/{max_retries})...")
                response = await client.post(registration_url, json=payload, headers=headers, timeout=10.0)
                
                if response.status_code == 200:
                    logger.info("Агент успешно зарегистрирован в Core Logic.")
                    return
                else:
                    logger.warning(
                        f"Регистрация не удалась. Core Logic вернул статус {response.status_code}. "
                        f"Ответ: {response.text}"
                    )

        except httpx.RequestError as e:
            logger.warning(f"Ошибка подключения к Core Logic при регистрации: {e}")
        
        if attempt < max_retries - 1:
            logger.info(f"Следующая попытка регистрации через {retry_delay} секунд.")
            await asyncio.sleep(retry_delay)
    
    logger.error("Не удалось зарегистрировать агента в Core Logic после всех попыток. Агент может работать некорректно.")


# --- Основное приложение FastAPI ---

app = FastAPI(
    title="Causabi Data Execution Agent",
    description="Безопасный сервис для выполнения запросов к данным клиента.",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.include_router(api_router)

# --- Обработчики событий и ошибок ---

@app.on_event("startup")
async def startup_event():
    """
    Выполняется при старте агента.
    """
    logger.info("Data Execution Agent запущен.")
    logger.info(f"Агент будет слушать на {settings.AGENT_HOST}:{settings.AGENT_PORT}")
    logger.info(f"Тип подключаемой БД: {settings.DB_DIALECT}")
    
    # Запускаем регистрацию в фоне, чтобы не блокировать старт сервера
    asyncio.create_task(register_agent())


@app.on_event("shutdown")
async def shutdown_event():
    """
    Выполняется при остановке агента.
    """
    logger.info("Data Execution Agent остановлен.")

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Глобальный обработчик исключений.
    """
    logger.error(f"Непредвиденная ошибка при обработке запроса {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Внутренняя ошибка агента: {exc}"},
    )

# --- Базовый эндпоинт для проверки ---

@app.get("/")
def read_root():
    return {"message": "Causabi Data Execution Agent is running."}