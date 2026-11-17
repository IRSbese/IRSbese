# ЧАСТЬ 3. Временные демонстрационные данные.

import sqlite3
from pathlib import Path

# Файл базы данных SQLite
DB_PATH = Path(__file__).resolve().with_name("products.db")

# SQL-скрипт с командами CREATE TABLE и INSERT
SQL_PATH = Path(__file__).resolve().with_name("init_db.sql")


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_db():
    """Создаёт таблицу и загружает данные из init_db.sql, если таблицы ещё нет."""
    connection = get_connection()

    try:
        table_exists = connection.execute("""
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'products'
        """).fetchone()

        if not table_exists:
            if not SQL_PATH.exists():
                raise FileNotFoundError(
                    f"Не найден SQL-файл: {SQL_PATH}"
                )

            sql_script = SQL_PATH.read_text(encoding="utf-8")
            connection.executescript(sql_script)
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


initialize_db()
products = get_products()