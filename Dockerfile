# Используем официальный образ Python
FROM python:3.11

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    libproj-dev \
    libjson-c-dev \
    build-essential \
    python3-dev \
    gfortran \
    libopenblas-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt /app/requirements.txt

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код агента
COPY . /app

# Открываем порт, на котором будет работать агент
EXPOSE 8080

# Команда для запуска агента
CMD ["uvicorn", "agent.main:app", "--host", "0.0.0.0", "--port", "8080"]