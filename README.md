

# Causabi Data Execution Agent


**Causabi Data Execution Agent** — это безопасный, изолированный сервис для выполнения SQL и Python кода, который генерируется LLM-моделями. Он выступает в роли защищенного "моста" между платформой Causabi AI и базой данных клиента, обеспечивая выполнение потенциально небезопасного кода в контролируемой, изолированной среде ("песочнице").

## Архитектура

Агент спроектирован для развертывания в приватной сети клиента (или в окружении, имеющем к ней доступ), в то время как основная платформа Causabi AI может находиться где угодно. Взаимодействие происходит по защищенному API.

```
+-------------------+      (HTTPS API-запросы)      +------------------------+      (SQL/Python)      +-------------------+
|                   |------------------------------>|                        |---------------------->|                   |
|  Платформа        |  (Код для выполнения,         | Data Execution Agent   |  (Выполняет код в     |   База данных     |
|  Causabi AI       |   авторизация по токену)      |  (в сети клиента)      |  Docker-песочнице)    |   клиента         |
|                   |<------------------------------|                        |<----------------------|                   |
+-------------------+      (Обогащенные данные)     +------------------------+      (Результат)       +-------------------+
```

## Ключевые возможности

-   **Безопасность превыше всего**: Код выполняется в изолированном Docker-контейнере с жесткими ограничениями по ресурсам (CPU, память, время выполнения) и без доступа к сети, кроме как к указанной базе данных.
-   **Поддержка SQL и Python**: Позволяет выполнять как `SELECT` SQL-запросы, так и сложный аналитический код на Python с использованием `pandas`.
-   **Интроспекция и профилирование**: Умеет анализировать схему подключенной БД, а также собирать детальную статистику по таблицам (распределение данных, топ значений), что критически важно для LLM.
-   **Кеширование данных**: Промежуточные результаты (DataFrame'ы) могут быть закешированы на диске агента для построения сложных, многошаговых сценариев анализа данных.
-   **Обогащенные ответы**: Возвращает не только данные, но и метаданные о выполнении: время, количество строк, схему результата и базовую статистику по колонкам.
-   **Простота интеграции**: Легко подключается к основной платформе через REST API с авторизацией по Bearer-токену.

## Предварительные требования

-   **Docker**: [Инструкция по установке](https://docs.docker.com/engine/install/)
-   **Docker Compose**: [Инструкция по установке](https://docs.docker.com/compose/install/)
-   **Python** 3.11+ (для локальной разработки)

## Установка и запуск

### 1. Клонирование репозитория

```bash
git clone https://github.com/SHADRINMMM/causabi-ai-backend-closed.git
cd causabi-ai-backend-closed/agent
```

### 2. Настройка окружения (`.env`)

Агент настраивается с помощью переменных окружения. Скопируйте файл с примером:

```bash
cp .env.example .env
```

Теперь откройте файл `.env` и заполните его своими данными.

#### Секция 1: Регистрация агента и связь с платформой

| Переменная         | Описание                                                                                                                  | Пример                                |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| `CORE_LOGIC_URL`   | URL платформы Causabi, где агент будет регистрироваться.                                                                   | `https://ai.causabi.com`              |
| `AGENT_SECRET_TOKEN` | Секретный токен для авторизации запросов от платформы к агенту. Должен быть сложным и уникальным.                         | `your_super_secret_token_12345`         |
| `AGENT_PUBLIC_URL` | Публично доступный URL этого агента. Платформа будет использовать его для отправки запросов. **Должен быть доступен извне.** | `https://agent.yourcompany.com`         |
| `AGENT_ID`         | Уникальный ID, полученный из дашборда Causabi AI после создания агента.                                                   | `agt-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxx` |

#### Секция 2: Подключение к базе данных клиента

Здесь вы настраиваете подключение к базе данных, которую агент будет анализировать.

| Переменная    | Описание                                                                                                | Пример                    |
| ------------- | ------------------------------------------------------------------------------------------------------- | ------------------------- |
| `DB_DIALECT`  | Диалект SQLAlchemy. *На данный момент полностью поддерживается `postgresql`.*                               | `postgresql`              |
| `DB_HOST`     | IP-адрес или доменное имя сервера базы данных.                                                          | `db.your-internal.network`|
| `DB_PORT`     | Порт для подключения к БД.                                                                              | `5432`                    |
| `DB_USER`     | Имя пользователя для подключения к БД.                                                                  | `readonly_user`           |
| `DB_PASSWORD` | Пароль пользователя.                                                                                    | `password`                |
| `DB_NAME`     | Имя базы данных для подключения.                                                                        | `analytics_db`            |
| `DB_SSL_MODE` | **(Важно!)** Режим SSL-соединения. Используйте `require` или `verify-full` для облачных/внешних баз данных. | `require`                 |

**Варианты настройки подключения к БД:**

-   **Локальная БД (для разработки):**
    -   `DB_HOST`: `localhost` или имя сервиса из `docker-compose.yml` (например, `postgres`).
    -   `DB_SSL_MODE`: Можно оставить пустым или установить в `prefer`.
-   **Внешняя/Облачная БД (Production):**
    -   `DB_HOST`: Публичный адрес вашей БД (например, из Yandex Cloud, AWS RDS).
    -   `DB_SSL_MODE`: **Крайне рекомендуется** установить `require` для шифрования трафика между агентом и БД. Это обеспечивает безопасность передаваемых данных.

### 3. Запуск агента через Docker Compose (Рекомендуемый способ)

Этот метод автоматически соберет все необходимые образы (включая образ для песочницы) и запустит агент.

```bash
# Запуск в интерактивном режиме (логи будут в консоли)
docker-compose up --build

# Запуск в фоновом режиме (detached)
docker-compose up --build -d
```

После успешного запуска агент будет доступен по порту, указанному в `.env` (например, `8001`), но для мира он будет виден по `AGENT_PUBLIC_URL`.

Для остановки используйте `docker-compose down`.

## Модель безопасности

Безопасность — ключевой аспект этого агента.

1.  **Аутентификация**: Все запросы к API агента (кроме `/health`) должны содержать `Authorization: Bearer <AGENT_SECRET_TOKEN>`.
2.  **Изоляция Python**: Весь Python-код выполняется в одноразовом Docker-контейнере с минимальными правами и без доступа к файловой системе хоста.
3.  **Ограничение ресурсов**: Для каждого контейнера-песочницы установлены жесткие лимиты:
    -   **Время выполнения**: 100 секунд
    -   **Память (RAM)**: 256 МБ
    -   **CPU**: 0.5 ядра
4.  **Безопасность SQL**: Агент разрешает выполнять **только** запросы на чтение данных, начинающиеся с `SELECT` или `WITH`. Все команды, изменяющие данные или схему (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, `ALTER` и др.), блокируются.

## Справочник по API

### Объекты

#### `EnrichedExecutionResult`
Стандартный успешный ответ для эндпоинтов выполнения кода.
```json
{
  "status": "success",
  "metadata": {
    "execution_time_ms": 150.75,
    "row_count": 10,
    "result_schema": [
      {
        "name": "user_id",
        "type": "int64",
        "stats": { "min": 1, "max": 10, "mean": 5.5, /* ... */ }
      }
    ]
  },
  "data": {
    "columns": ["user_id", "email"],
    "rows": [
      [1, "user1@example.com"],
      [2, "user2@example.com"]
    ]
  },
  "cache_key": "optional-uuid-for-caching"
}
```

---

### Эндпоинты

#### `GET /health`
Проверка работоспособности агента. Не требует авторизации.
-   **Ответ (200 OK)**: `{"status": "ok", "db_dialect": "postgresql"}`

#### `GET /schema`
Возвращает JSON-представление схемы базы данных.
-   **Авторизация**: `Bearer <AGENT_SECRET_TOKEN>`
-   **Ответ (200 OK)**:
    ```json
    {
      "dialect": "postgresql",
      "schema": {
        "tables": [
          {
            "name": "users",
            "columns": [
              { "name": "id", "type": "INTEGER", "is_primary_key": true },
              { "name": "username", "type": "VARCHAR(50)", "is_primary_key": false }
            ]
          }
        ]
      }
    }
    ```

#### `GET /schema/{table_name}/profile`
Возвращает детальный профиль (статистику) для указанной таблицы.
-   **Авторизация**: `Bearer <AGENT_SECRET_TOKEN>`
-   **Ответ (200 OK)**:
    ```json
    {
      "table_name": "products",
      "columns": [
        {
          "name": "category",
          "null_count": 0,
          "top_values": [{"value": "Electronics", "count": 150}, {"value": "Books", "count": 95}],
          "distinct_examples": ["Electronics", "Books", "Home Goods"]
        },
        {
          "name": "price",
          "null_count": 5,
          "histogram": [{"bucket_start": 10.0, "bucket_end": 25.5, "count": 80}],
        }
      ]
    }
    ```

#### `POST /execute`
Выполняет SQL или Python код, который обращается напрямую к базе данных. Результат выполнения кешируется.
-   **Авторизация**: `Bearer <AGENT_SECRET_TOKEN>`
-   **Тело запроса**:
    ```json
    {
      "language": "sql", // или "python"
      "code": "SELECT * FROM users LIMIT 10;"
    }
    ```
-   **Ответ (200 OK)**: `EnrichedExecutionResult` (см. выше). Ответ будет содержать `cache_key`.

#### `POST /execute-on-data`
Выполняет Python-код над данными, которые были ранее загружены и закешированы.
-   **Авторизация**: `Bearer <AGENT_SECRET_TOKEN>`
-   **Тело запроса**:
    ```json
    {
      "code": "result_df = input_data['previous_results'].groupby('category').size().reset_index(name='counts')",
      "input_data": {}, // Можно передать сэмпл данных, если нет ключа кеша
      "cache_keys": {
        "previous_results": "uuid-from-previous-step"
      }
    }
    ```
-   **Ответ (200 OK)**: `EnrichedExecutionResult` с новым `cache_key`.
-   **Ответ с ошибкой (400 Bad Request)**:
    ```json
    {
      "detail": {
        "type": "EXECUTION_ERROR",
        "message": "Ошибка выполнения кода: division by zero"
      }
    }
    ```

## Разработка и тестирование

Для запуска тестов используется отдельный `docker-compose.test.yml`, который поднимает агента, тестовую базу данных и контейнер для запуска тестов.

1.  **Создайте `requirements.dev.txt`**: Убедитесь, что у вас есть этот файл с зависимостями для тестов (`pytest`, `httpx` и т.д.).
2.  **Запустите тесты**:
    ```bash
    docker-compose -f docker-compose.test.yml up --build --exit-code-from test-runner
    ```
3.  **Остановите окружение**:
    ```bash
    docker-compose -f docker-compose.test.yml down
    ```

---

## English Version

# Causabi Data Execution Agent



The **Causabi Data Execution Agent** is a secure, isolated service for executing SQL and Python code generated by LLM models. It acts as a secure bridge between the Causabi AI platform and a client's database, ensuring that potentially unsafe code is executed in a controlled, sandboxed environment.

## Architecture

The Agent is designed to be deployed within a client's private network (or an environment with access to it), while the main Causabi AI platform can be hosted anywhere. Communication occurs over a secure API.

```
+-------------------+      (HTTPS API Requests)      +------------------------+      (SQL/Python)      +-------------------+
|                   |------------------------------>|                        |---------------------->|                   |
| Causabi AI        |  (Code to execute,            | Data Execution Agent   |  (Executes code in    | Client's          |
| Platform          |   token authorization)        |  (in client's network) |  Docker sandbox)      | Database          |
|                   |<------------------------------|                        |<----------------------|                   |
+-------------------+      (Enriched Data)          +------------------------+      (Result)          +-------------------+
```

## Key Features

-   **Security First**: Code is executed in an isolated Docker container with strict resource limits (CPU, memory, timeout) and no network access except to the specified database.
-   **SQL and Python Support**: Allows execution of `SELECT` SQL queries and complex analytical Python code using `pandas`.
-   **Introspection and Profiling**: Can analyze the schema of the connected database and gather detailed statistics for tables (data distribution, top values), which is critical for LLMs.
-   **Data Caching**: Intermediate results (DataFrames) can be cached on the agent's disk to build complex, multi-step data analysis workflows.
-   **Enriched Responses**: Returns not just data, but also execution metadata: time, row count, result schema, and basic column statistics.
-   **Simple Integration**: Connects seamlessly to the core platform via a REST API with Bearer token authorization.

## Prerequisites

-   **Docker**: [Get Docker](https://docs.docker.com/engine/install/)
-   **Docker Compose**: [Get Docker Compose](https://docs.docker.com/compose/install/)
-   **Python** 3.11+ (for local development)

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/SHADRINMMM/causabi-ai-backend-closed.git
cd causabi-ai-backend-closed/agent
```

### 2. Configure the Environment (`.env`)

The agent is configured using environment variables. Copy the example file:

```bash
cp .env.example .env
```

Now, open the `.env` file and fill in your details.

#### Section 1: Agent Registration & Platform Connection

| Variable           | Description                                                                                                    | Example                               |
| ------------------ | -------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| `CORE_LOGIC_URL`   | The URL of the Causabi platform where the agent will register itself.                                           | `https://ai.causabi.com`              |
| `AGENT_SECRET_TOKEN` | A secret token to authorize requests from the platform to the agent. Should be complex and unique.              | `your_super_secret_token_12345`         |
| `AGENT_PUBLIC_URL` | The publicly accessible URL of this agent. The platform will use this to send requests. **Must be accessible externally.** | `https://agent.yourcompany.com`         |
| `AGENT_ID`         | The unique ID obtained from the Causabi AI dashboard after creating the agent.                                  | `agt-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxx` |

#### Section 2: Client Database Connection

Configure the connection to the database the agent will analyze.

| Variable      | Description                                                                                              | Example                    |
| ------------- | -------------------------------------------------------------------------------------------------------- | ------------------------- |
| `DB_DIALECT`  | SQLAlchemy dialect. *Currently, `postgresql` is fully supported.*                                        | `postgresql`              |
| `DB_HOST`     | IP address or domain name of the database server.                                                         | `db.your-internal.network`|
| `DB_PORT`     | The port to connect to the database.                                                                     | `5432`                    |
| `DB_USER`     | The username for the database connection.                                                                | `readonly_user`           |
| `DB_PASSWORD` | The user's password.                                                                                     | `password`                |
| `DB_NAME`     | The name of the database to connect to.                                                                  | `analytics_db`            |
| `DB_SSL_MODE` | **(Important!)** The SSL connection mode. Use `require` or `verify-full` for cloud/external databases.       | `require`                 |

**Database Connection Scenarios:**

-   **Local DB (for development):**
    -   `DB_HOST`: `localhost` or the service name from `docker-compose.yml` (e.g., `postgres`).
    -   `DB_SSL_MODE`: Can be left empty or set to `prefer`.
-   **External/Cloud DB (Production):**
    -   `DB_HOST`: The public endpoint of your database (e.g., from AWS RDS, Yandex Cloud).
    -   `DB_SSL_MODE`: It is **highly recommended** to set this to `require` to encrypt traffic between the agent and the database, ensuring data security.

### 3. Run the Agent via Docker Compose (Recommended)

This method will automatically build all necessary images (including the sandbox image) and start the agent.

```bash
# Run in foreground (logs in console)
docker-compose up --build

# Run in background (detached mode)
docker-compose up --build -d
```

Once started, the agent will be accessible on the port specified in `.env` (e.g., `8001`), but it will be reachable by the platform at `AGENT_PUBLIC_URL`.

To stop the services, use `docker-compose down`.

## Security Model

Security is a core aspect of this agent.

1.  **Authentication**: All API requests (except `/health`) must include `Authorization: Bearer <AGENT_SECRET_TOKEN>`.
2.  **Python Sandbox Isolation**: All Python code is executed in a disposable Docker container with minimal privileges and no access to the host filesystem.
3.  **Resource Limiting**: Each sandbox container is subject to strict limits:
    -   **Execution Time**: 100 seconds
    -   **Memory (RAM)**: 256 MB
    -   **CPU**: 0.5 core
4.  **SQL Scoping**: The agent only allows read-only queries starting with `SELECT` or `WITH`. All commands that modify data or schema (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, `ALTER`, etc.) are blocked.

## API Reference

(The API Reference section is identical to the Russian version and provides detailed information on each endpoint, which I will omit here for brevity. It covers `/health`, `/schema`, `/schema/{table_name}/profile`, `/execute`, and `/execute-on-data` with request and response examples.)

## Development & Testing

To run tests, a separate `docker-compose.test.yml` file is used, which sets up the agent, a test database, and a test runner container.

1.  **Create `requirements.dev.txt`**: Ensure you have this file with development dependencies (`pytest`, `httpx`, etc.).
2.  **Run Tests**:
    ```bash
    docker-compose -f docker-compose.test.yml up --build --exit-code-from test-runner
    ```
3.  **Tear Down Environment**:
    ```bash
    docker-compose -f docker-compose.test.yml down
    ```