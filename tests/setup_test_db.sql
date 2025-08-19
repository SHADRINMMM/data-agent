-- tests/setup_test_db.sql

-- Создаем таблицы для тестов
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    user_id INTEGER REFERENCES users(id)
);

-- Вставляем тестовые данные
INSERT INTO users (username) VALUES ('testuser1'), ('testuser2');

INSERT INTO products (name, price, user_id) VALUES
('Laptop', 1200.50, 1),
('Mouse', 25.00, 1),
('Keyboard', 75.99, 2);