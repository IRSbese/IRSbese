# ЧАСТЬ 3. База данных и взаимодействие с ней.

import sqlite3
from pathlib import Path
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Файл базы данных SQLite
DB_PATH = Path(__file__).resolve().with_name("products.db")

# SQL-скрипт с командами CREATE TABLE и INSERT
SQL_PATH = Path(__file__).resolve().with_name("init_db.sql")

ph = PasswordHasher()

def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_db():
    """Создаёт таблицы и загружает данные из init_db.sql, если их ещё нет."""
    connection = get_connection()

    try:
        # Получаем список всех существующих таблиц в базе данных
        existing_tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

        # Проверяем, что обе нужные таблицы есть
        if "products" not in existing_tables or "users" not in existing_tables:
            if not SQL_PATH.exists():
                raise FileNotFoundError(
                    f"Не найден SQL-файл: {SQL_PATH}"
                )

            sql_script = SQL_PATH.read_text(encoding="utf-8")
            connection.executescript(sql_script)
            connection.commit()  # Добавлено для надежности сохранения
    finally:
        connection.close()


def check_user_credentials(login, password):
    """
    Проверяет логин и пароль.
    Возвращает словарь с данными пользователя (id, username, email) при успехе,
    или None, если пароль неверный или пользователь не найден.
    """
    connection = get_connection()
    try:
        # Ищем по username или email
        row = connection.execute(
            "SELECT id, username, email, password_hash FROM users WHERE username = ? OR email = ?",
            (login, login.lower()),
        ).fetchone()
    finally:
        connection.close()

    if not row:
        return None

    try:
        # Проверяем хэш
        ph.verify(row["password_hash"], password)
        return dict(row)
    except VerifyMismatchError:
        return None


def create_user(username, email, password):
    """
    Создаёт пользователя с Argon2id-хэшем пароля.
    Возвращает True при успехе или False, если логин/email уже заняты.
    """
    password_hash = ph.hash(password)
    connection = get_connection()
    try:
        connection.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash),
        )
        connection.commit()
        return True
    except sqlite3.IntegrityError:
        # Срабатывает, если username или email уже есть в базе (UNIQUE)
        return False
    finally:
        connection.close()


def get_products():
    connection = get_connection()

    try:
        rows = connection.execute("""
            SELECT id, name, category, price, description, image
            FROM products
            ORDER BY id
        """).fetchall()

        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_product(product_id):
    connection = get_connection()

    try:
        row = connection.execute("""
            SELECT id, name, category, price, description, image
            FROM products
            WHERE id = ?
        """, (product_id,)).fetchone()

        return dict(row) if row else None
    finally:
        connection.close()


def search_products(query_text):
    """Ищет товары по названию или категории через базу данных."""
    connection = get_connection()
    try:
        if not query_text:
            # Если поиск пустой, возвращаем все товары
            rows = connection.execute(
                "SELECT id, name, category, price, description, image FROM products ORDER BY id"
            ).fetchall()
        else:
            # SQL-запрос с поиском по названию ИЛИ категории
            search_pattern = f"%{query_text}%"
            rows = connection.execute(
                "SELECT id, name, category, price, description, image FROM products WHERE name LIKE ? OR category LIKE ? ORDER BY id",
                (search_pattern, search_pattern)
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


initialize_db()