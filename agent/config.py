from typing import Optional
from urllib.parse import quote_plus

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

class AgentSettings(BaseSettings):
    """
    Настройки для Data Execution Agent.
    Загружает значения из переменных окружения.
    """

    # --- Секция 1: Идентификация и Связь с Core Logic ---
    # URL основного бэкенда, куда агент будет отправлять "ping" для регистрации.
    CORE_LOGIC_URL: str
    # Секретный токен, который агент использует для аутентификации перед Core Logic.
    AGENT_SECRET_TOKEN: str
    # Публично доступный URL самого агента. Он отправит этот URL в Core Logic,
    # чтобы тот знал, по какому адресу к нему обращаться.
    AGENT_PUBLIC_URL: str

    # --- Секция 2: Подключение к Базе Данных Клиента ---
    DB_DIALECT: str   # Например, "postgresql", "mysql"
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    # Опциональный параметр для SSL, например "require" для облачных БД.
    DB_SSL_MODE: Optional[str] = None

    # --- Секция 3: Настройки Docker ---
    # Имя сети Docker, к которой будет подключаться песочница.
    # Если не указано, будет определено автоматически.
    DOCKER_NETWORK: Optional[str] = None

    # --- Секция 4: Настройки Веб-сервера Агента ---
    AGENT_HOST: str = "0.0.0.0"
    AGENT_PORT: int = 8001

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        """
        Динамически собирает SQLAlchemy URL для подключения к БД клиента.
        Использует `quote_plus` для безопасного кодирования пароля.
        """
        # Кодируем пароль на случай, если в нем есть спецсимволы
        encoded_password = quote_plus(self.DB_PASSWORD)
        
        url = (
            f"postgresql+psycopg://"
            f"{self.DB_USER}:{encoded_password}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
        if self.DB_SSL_MODE:
            url += f"?sslmode={self.DB_SSL_MODE}"
        return url

    # Конфигурация Pydantic для чтения из .env файла
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra="ignore"
    )

# Создаем единственный экземпляр настроек, который будет использоваться во всем агенте
settings = AgentSettings()