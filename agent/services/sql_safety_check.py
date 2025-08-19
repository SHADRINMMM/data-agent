# agent/services/sql_safety_check.py

import re
from typing import Tuple

# Набор запрещенных ключевых слов, которые изменяют данные или структуру
# (DDL/DML). Мы будем проверять их наличие.
# Они должны быть в нижнем регистре.
FORBIDDEN_KEYWORDS = {
    'insert', 'update', 'delete', 'drop', 'create', 'alter', 'truncate',
    'grant', 'revoke', 'commit', 'rollback', 'savepoint', 'call'
}

# Ключевые слова, с которых может начинаться безопасный запрос.
ALLOWED_START_KEYWORDS = {'select', 'with'}

def is_sql_safe(sql_query: str, dialect: str) -> Tuple[bool, str]:
    """
    Проверяет SQL-запрос на безопасность.

    Правила:
    1. Запрос должен быть одной командой (не содержать ';', кроме как в конце).
    2. Он не должен содержать запрещенных DML/DDL ключевых слов.
    3. Он должен начинаться с 'SELECT' или 'WITH'.

    :param sql_query: Строка с SQL-запросом.
    :param dialect: Диалект SQL (пока не используется, но зарезервирован).
    :return: Кортеж (is_safe: bool, message: str).
    """
    if not sql_query or not sql_query.strip():
        return False, "Пустой SQL-запрос не разрешен."

    # 1. Удаляем комментарии, чтобы они не мешали анализу
    # Удаляем многострочные комментарии /* ... */
    query = re.sub(r'/\*.*?\*/', '', sql_query, flags=re.DOTALL)
    # Удаляем однострочные комментарии -- ...
    query = re.sub(r'--.*', '', query)

    # Приводим к нижнему регистру для регистронезависимой проверки
    clean_query = query.lower().strip()

    # 2. Проверяем наличие нескольких операторов
    # Разделяем по ';' и удаляем пустые строки, которые могут появиться,
    # если запрос заканчивается на ';'
    statements = [s.strip() for s in clean_query.split(';') if s.strip()]

    if len(statements) > 1:
        return False, "Множественные SQL-команды в одном запросе запрещены."
    
    if not statements:
         return False, "Запрос не содержит исполняемых команд после очистки."

    # 3. Проверяем, с чего начинается единственный оператор
    # Используем split() без аргументов для обработки любого количества пробелов
    statement_words = statements[0].strip().split()
    if not statement_words:
        return False, "Запрос не содержит исполняемых команд."
        
    first_word = statement_words[0]
    if first_word not in ALLOWED_START_KEYWORDS:
        return False, f"Разрешены только запросы, начинающиеся с SELECT или WITH. Ваш запрос начинается с '{first_word.upper()}'."

    # 4. Проверяем на наличие запрещенных слов в единственном операторе
    # Мы используем \b для поиска целых слов, чтобы 'users_update' не считалось 'update'
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(r'\b' + keyword + r'\b', statements[0]):
            return False, f"Обнаружена небезопасная SQL-конструкция: '{keyword.upper()}'."

    return True, "Запрос выглядит безопасным."
