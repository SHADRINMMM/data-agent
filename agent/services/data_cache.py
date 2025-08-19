# agent/services/data_cache.py
import uuid
from pathlib import Path
import pandas as pd
from loguru import logger
import os
from datetime import datetime, timedelta

CACHE_DIR = Path("./.data_cache")
CACHE_DIR.mkdir(exist_ok=True)
# --- НОВЫЕ КОНСТАНТЫ ---
CACHE_TTL_HOURS = 12  # Время жизни файла в часах
CACHE_MAX_SIZE_MB = 512  # Максимальный размер папки кеша в МБ
CACHE_CLEANUP_TARGET_MB = 400 # До какого размера чистить (чтобы не чистить по 1 файлу)
# ----------------------

class AgentDataCache:
    """Дисковый кеш для DataFrame'ов с TTL и ограничением по размеру."""

    def __init__(self):
        self._ttl = timedelta(hours=CACHE_TTL_HOURS)
        self._max_size_bytes = CACHE_MAX_SIZE_MB * 1024 * 1024
        self._cleanup_target_bytes = CACHE_CLEANUP_TARGET_MB * 1024 * 1024

    def _cleanup(self):
        """Запускает очистку кеша: сначала по TTL, потом по размеру (LRU)."""
        logger.info("Запуск очистки кеша...")
        now = datetime.now()
        files_with_meta = []
        current_size = 0

        # Собираем метаданные файлов
        for entry in CACHE_DIR.iterdir():
            if entry.is_file() and entry.suffix == '.parquet':
                try:
                    stat = entry.stat()
                    files_with_meta.append({
                        "path": entry,
                        "size": stat.st_size,
                        "atime": stat.st_atime, # Время последнего доступа
                        "mtime": stat.st_mtime  # Время последней модификации
                    })
                    current_size += stat.st_size
                except FileNotFoundError:
                    continue # Файл мог быть удален другим процессом

        # 1. Очистка по TTL
        expired_files = [
            f for f in files_with_meta
            if now - datetime.fromtimestamp(f["mtime"]) > self._ttl
        ]
        if expired_files:
            logger.info(f"Найдено {len(expired_files)} просроченных файлов для удаления...")
            for f in expired_files:
                try:
                    os.remove(f["path"])
                    current_size -= f["size"]
                except OSError as e:
                    logger.warning(f"Не удалось удалить просроченный файл кеша {f['path']}: {e}")

        # 2. Очистка по размеру (LRU - удаляем самые старые по доступу)
        if current_size > self._max_size_bytes:
            logger.info(f"Размер кеша ({current_size / 1024**2:.2f} MB) превышает лимит ({CACHE_MAX_SIZE_MB} MB). Запускаю LRU-очистку.")
            # Сортируем оставшиеся файлы по времени последнего доступа (самые старые сначала)
            remaining_files = [f for f in files_with_meta if f not in expired_files]
            remaining_files.sort(key=lambda x: x["atime"])

            while current_size > self._cleanup_target_bytes and remaining_files:
                file_to_delete = remaining_files.pop(0)
                try:
                    os.remove(file_to_delete["path"])
                    current_size -= file_to_delete["size"]
                    logger.info(f"Удален старый файл: {file_to_delete['path'].name}")
                except OSError as e:
                    logger.warning(f"Не удалось удалить старый файл кеша {file_to_delete['path']}: {e}")

    def save(self, df: pd.DataFrame) -> str:
        """Сохраняет DataFrame и запускает очистку."""
        self._cleanup() # Запускаем очистку перед каждым сохранением
        cache_key = str(uuid.uuid4())
        file_path = CACHE_DIR / f"{cache_key}.parquet"
        try:
            df.to_parquet(file_path, index=False)
            logger.info(f"DataFrame сохранен в кеш. Ключ: {cache_key}")
            return cache_key
        except Exception as e:
            logger.error(f"Не удалось сохранить DataFrame в кеш: {e}")
            raise

    def load(self, cache_key: str) -> pd.DataFrame:
        """Загружает DataFrame и обновляет время доступа к файлу."""
        file_path = CACHE_DIR / f"{cache_key}.parquet"
        if not file_path.exists():
            logger.error(f"Ключ кеша не найден: {cache_key}")
            raise FileNotFoundError(f"Cache key {cache_key} not found.")
        try:
            # Обновляем время доступа, чтобы LRU-логика работала корректно
            file_path.touch(exist_ok=True)
            df = pd.read_parquet(file_path)
            logger.info(f"DataFrame загружен из кеша по ключу: {cache_key}")
            return df
        except Exception as e:
            logger.error(f"Не удалось загрузить DataFrame из кеша: {e}")
            raise
