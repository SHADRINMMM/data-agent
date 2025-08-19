# agent/sandbox/run_sandbox.py
import os
import sys
import io
import json
import pandas as pd
from sqlalchemy import create_engine
import time
import numpy as np

def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return None
    try:
        engine = create_engine(db_url)
        return engine.connect()
    except Exception as e:
        print(f"Error creating database connection: {e}", file=sys.stderr)
        return None

def main():
    start_time = time.monotonic()
    
    code_to_execute = os.getenv("PYTHON_CODE_TO_EXECUTE")
    input_data_json = os.getenv("INPUT_DATA_JSON")

    if not code_to_execute:
        print("Ошибка: PYTHON_CODE_TO_EXECUTE не установлена.", file=sys.stderr)
        sys.exit(1)

    execution_globals = {"get_db_connection": get_db_connection, "pd": pd}
    execution_locals = {}

    if input_data_json:
        try:
            input_data_dict = json.loads(input_data_json)
            deserialized_dfs = {}
            for var_name, data_json in input_data_dict.items():
                # data_json - это уже python dict. Превращаем его обратно в строку для pd.read_json
                json_str = json.dumps(data_json)
                deserialized_dfs[var_name] = pd.read_json(io.StringIO(json_str), orient='split')
            execution_locals["input_data"] = deserialized_dfs
        except Exception as e:
            print(f"Критическая ошибка десериализации входных данных: {e}", file=sys.stderr)
            sys.exit(1)
    
    try:
        exec(code_to_execute, execution_globals, execution_locals)

        if 'result_df' not in execution_locals:
            print("Ошибка: Код не создал результирующую переменную 'result_df'.", file=sys.stderr)
            sys.exit(1)

        result_df = execution_locals['result_df']
        if not isinstance(result_df, pd.DataFrame):
            print(f"Ошибка: Переменная 'result_df' имеет тип {type(result_df)}, а не pandas.DataFrame.", file=sys.stderr)
            sys.exit(1)

        # --- НОВАЯ ЛОГИКА: ФОРМИРОВАНИЕ ОБОГАЩЕННОГО ОТВЕТА ---
        exec_time_ms = (time.monotonic() - start_time) * 1000

        # 1. Рассчитываем метаданные колонок
        column_metadata_list = []
        for col_name in result_df.columns:
            col_series = result_df[col_name]
            col_type = str(col_series.dtype)
            stats = None

            if pd.api.types.is_numeric_dtype(col_series.dtype):
                desc = col_series.describe()
                stats = {
                    "min": desc.get('min'), "max": desc.get('max'), "mean": desc.get('mean'),
                    "std_dev": desc.get('std'), "unique_count": int(col_series.nunique())
                }
            elif pd.api.types.is_datetime64_any_dtype(col_series.dtype):
                stats = {
                    "min": str(col_series.min()) if pd.notna(col_series.min()) else None,
                    "max": str(col_series.max()) if pd.notna(col_series.max()) else None,
                    "unique_count": int(col_series.nunique())
                }
            else:
                stats = {"unique_count": int(col_series.nunique())}
            
            column_metadata_list.append({"name": col_name, "type": col_type, "stats": stats})

        # 2. Формируем финальный JSON
        enriched_result = {
            "status": "success",
            "metadata": {
                "execution_time_ms": exec_time_ms, # Это время внутри контейнера
                "row_count": len(result_df),
                "result_schema": column_metadata_list
            },
            "data": {
                "columns": result_df.columns.tolist(),
                "rows": result_df.where(pd.notna(result_df), None).values.tolist()
            }
        }
        
        # Функция для конвертации numpy типов в стандартные типы Python для JSON
        def convert_numpy(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj

        print(json.dumps(enriched_result, default=convert_numpy))

    except Exception as e:
        print(f"Ошибка выполнения кода: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()