# agent/sandbox/Dockerfile
FROM python:3.11

WORKDIR /sandbox

# Устанавливаем зависимости: pandas и драйвер для PostgreSQL
RUN pip install pandas sqlalchemy psycopg2-binary

# Копируем и запускаем скрипт-обертку
COPY agent/sandbox/run_sandbox.py .

# Код для выполнения будет передан через переменную окружения
# $PYTHON_CODE_TO_EXECUTE
CMD ["python", "run_sandbox.py"]