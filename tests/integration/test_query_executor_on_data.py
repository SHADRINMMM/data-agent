import pytest
from typing import Dict, Any
import pandas as pd

from agent.services.query_executor import query_executor

# Fixture to create a sample DataFrame
@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    return pd.DataFrame({
        'A': [1, 2, 3],
        'B': [4, 5, 6]
    })

# Fixture to create the input data dictionary
@pytest.fixture
def input_data(sample_dataframe: pd.DataFrame) -> Dict[str, Any]:
    return {
        "my_df": json.loads(sample_dataframe.to_json(orient='split'))
    }

@pytest.mark.asyncio
async def test_run_python_on_data_happy_path(input_data: Dict[str, Any]):
    """
    Тест успешного выполнения кода, который обрабатывает входные данные.
    """
    code = "result_df = input_data['my_df'].head(1)"
    
    result = await query_executor.run_python_on_data(
        python_code=code,
        input_data=input_data
    )
    
    assert result["status"] == "success"
    assert "result" in result
    
    # Проверяем, что результат - это корректный JSON от pandas
    result_data = result["result"]
    assert result_data["columns"] == ["A", "B"]
    assert len(result_data["data"]) == 1
    assert result_data["data"][0] == [1, 4]

@pytest.mark.asyncio
async def test_run_python_on_data_execution_error(input_data: Dict[str, Any]):
    """
    Тест на обработку ошибки выполнения кода в песочнице.
    """
    code = "result_df = input_data['my_df'] / 0" # Ошибка деления на ноль
    
    result = await query_executor.run_python_on_data(
        python_code=code,
        input_data=input_data
    )
    
    assert result["status"] == "error"
    assert result["error"]["type"] == "EXECUTION_ERROR"
    assert "unsupported operand type(s)" in result["error"]["message"]

@pytest.mark.asyncio
async def test_run_python_on_data_serialization_error():
    """
    Тест на обработку ошибки сериализации данных (до запуска Docker).
    """
    # Объекты класса не сериализуются в JSON по умолчанию
    class NonSerializable:
        pass

    input_data = {"my_data": NonSerializable()}
    
    result = await query_executor.run_python_on_data(
        python_code="result_df = pd.DataFrame()",
        input_data=input_data
    )
    
    assert result["status"] == "error"
    assert result["error"]["type"] == "SERIALIZATION_ERROR"
    assert "not JSON serializable" in result["error"]["message"]

@pytest.mark.asyncio
async def test_run_python_on_data_no_result_df_error(input_data: Dict[str, Any]):
    """
    Тест на случай, когда код не создает переменную result_df.
    """
    code = "x = 1" # Не создает result_df
    
    result = await query_executor.run_python_on_data(
        python_code=code,
        input_data=input_data
    )
    
    assert result["status"] == "error"
    assert result["error"]["type"] == "EXECUTION_ERROR"
    assert "Код не создал результирующую переменную 'result_df'" in result["error"]["message"]