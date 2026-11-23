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

        # Проверяем наличие ВСЕХ нужных таблиц
        required_tables = {"products", "users", "cart", "orders", "order_items"}
        
        # Если хотя бы одной таблицы нет — запускаем SQL-скрипт
        if not required_tables.issubset(existing_tables):
            if not SQL_PATH.exists():
                raise FileNotFoundError(
                    f"Не найден SQL-файл: {SQL_PATH}"
                )

            sql_script = SQL_PATH.read_text(encoding="utf-8")
            connection.executescript(sql_script)
            connection.commit()
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

# ---------- КОРЗИНА ----------

def add_to_cart(user_id, product_id):
    """Добавляет товар в корзину или увеличивает его количество."""
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT id, quantity FROM cart WHERE user_id = ? AND product_id = ?",
            (user_id, product_id)
        ).fetchone()

        if row:
            connection.execute(
                "UPDATE cart SET quantity = quantity + 1 WHERE id = ?",
                (row["id"],)
            )
        else:
            connection.execute(
                "INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, 1)",
                (user_id, product_id)
            )
        connection.commit()
    finally:
        connection.close()


def get_cart_items(user_id):
    """Возвращает список товаров в корзине."""
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT c.id as cart_id, c.quantity, p.id as product_id, p.name, p.price, p.image
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = ?
        """, (user_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def remove_from_cart(cart_id):
    """Удаляет товар из корзины."""
    connection = get_connection()
    try:
        connection.execute("DELETE FROM cart WHERE id = ?", (cart_id,))
        connection.commit()
    finally:
        connection.close()


# ---------- ЗАКАЗЫ ----------

def create_order(user_id):
    """Переносит товары из корзины в заказ."""
    connection = get_connection()
    try:
        cart_items = connection.execute("""
            SELECT c.quantity, p.price, p.id as product_id
            FROM cart c JOIN products p ON c.product_id = p.id
            WHERE c.user_id = ?
        """, (user_id,)).fetchall()

        if not cart_items:
            return False

        total_price = sum(item["price"] * item["quantity"] for item in cart_items)

        cursor = connection.execute(
            "INSERT INTO orders (user_id, total_price) VALUES (?, ?)",
            (user_id, total_price)
        )
        order_id = cursor.lastrowid

        for item in cart_items:
            connection.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                (order_id, item["product_id"], item["quantity"], item["price"])
            )

        connection.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        connection.commit()
        return order_id
    except Exception:
        connection.rollback()
        return False
    finally:
        connection.close()


def get_user_orders(user_id):
    """Возвращает историю заказов пользователя."""
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT id, total_price, created_at FROM orders WHERE user_id = ? ORDER BY id DESC",
            (user_id,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()

def increase_cart_item(cart_id):
    """Увеличивает количество товара в корзине на 1."""
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE cart SET quantity = quantity + 1 WHERE id = ?",
            (cart_id,)
        )
        connection.commit()
    finally:
        connection.close()


def decrease_cart_item(cart_id):
    """Уменьшает количество товара на 1. Если становится 0 — удаляет."""
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT quantity FROM cart WHERE id = ?", (cart_id,)
        ).fetchone()
        
        if row and row["quantity"] > 1:
            connection.execute(
                "UPDATE cart SET quantity = quantity - 1 WHERE id = ?",
                (cart_id,)
            )
        else:
            # Если количество 1 или меньше — удаляем товар
            connection.execute("DELETE FROM cart WHERE id = ?", (cart_id,))
            
        connection.commit()
    finally:
        connection.close()


initialize_db()