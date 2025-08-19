# agent/schemas.py
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
import datetime

class ColumnStats(BaseModel):
    """Статистика для одного столбца."""
    min: Optional[Union[float, str]] = Field(None, description="Минимальное значение.")
    max: Optional[Union[float, str]] = Field(None, description="Максимальное значение.")
    mean: Optional[float] = Field(None, description="Среднее арифметическое (для числовых данных).")
    std_dev: Optional[float] = Field(None, description="Стандартное отклонение (для числовых данных).")
    unique_count: Optional[int] = Field(None, description="Количество уникальных значений.")

class HistogramBin(BaseModel):
    """Описывает один "столбец" гистограммы."""
    bucket_start: float
    bucket_end: float
    count: int

class TopValue(BaseModel):
    """Описывает одно из самых частых значений в столбце."""
    value: Any
    count: int

class ColumnProfile(BaseModel):
    """Расширенная статистика (профиль) для одного столбца."""
    name: str
    null_count: int
    # Одно из полей будет заполнено в зависимости от типа столбца
    histogram: Optional[List[HistogramBin]] = None
    top_values: Optional[List[TopValue]] = None
    distinct_examples: Optional[List[Any]] = Field(None, description="Примеры уникальных значений из столбца.")

class TableProfile(BaseModel):
    """Полный профиль таблицы, состоящий из профилей столбцов."""
    table_name: str
    columns: List[ColumnProfile]

class ColumnMetadata(BaseModel):
    """Метаданные для одного столбца результата."""
    name: str = Field(..., description="Имя столбца.")
    type: str = Field(..., description="Тип данных столбца (pandas dtype).")
    stats: Optional[ColumnStats] = Field(None, description="Рассчитанная статистика, если применимо.")

class ExecutionMetadata(BaseModel):
    """Метаданные о выполнении запроса."""
    execution_time_ms: float = Field(..., description="Время выполнения запроса в миллисекундах.")
    row_count: int = Field(..., description="Количество строк в результате.")
    result_schema: List[ColumnMetadata] = Field(..., description="Схема (колонки и их типы) результата.")

class ExecutionData(BaseModel):
    """Непосредственно данные результата."""
    columns: List[str]
    rows: List[List[Any]]

class EnrichedExecutionResult(BaseModel):
    """
    Финальная обогащенная структура ответа от эндпоинтов /execute и /execute-on-data.
    """
    status: str = Field("success", description="Статус выполнения.")
    metadata: ExecutionMetadata
    data: ExecutionData
