# ЧАСТЬ 2. SQLite: соединение, таблицы, индексы и стартовые данные.
import sqlite3
from pathlib import Path
from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL,
 email TEXT UNIQUE,
 phone TEXT UNIQUE,
 password_hash TEXT NOT NULL,
 role TEXT NOT NULL DEFAULT 'buyer' CHECK(role IN ('buyer','seller')),
 company_name TEXT NOT NULL DEFAULT '',
 inn TEXT NOT NULL DEFAULT '',
 seller_status TEXT NOT NULL DEFAULT 'approved',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS products (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 seller_id INTEGER REFERENCES users(id),
 name TEXT NOT NULL,
 category TEXT NOT NULL,
 price REAL NOT NULL CHECK(price >= 0),
 description TEXT NOT NULL,
 image TEXT NOT NULL DEFAULT '',
 stock INTEGER NOT NULL DEFAULT 1 CHECK(stock >= 0),
 active INTEGER NOT NULL DEFAULT 1,
 moderation_status TEXT NOT NULL DEFAULT 'approved',
 is_adult INTEGER NOT NULL DEFAULT 0 CHECK(is_adult IN (0,1)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS orders (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id),
 total REAL NOT NULL,
 status TEXT NOT NULL DEFAULT 'Новый',
 customer_name TEXT NOT NULL,
 phone TEXT NOT NULL,
 address TEXT NOT NULL,
 delivery_method TEXT NOT NULL DEFAULT 'Курьер',
 comment TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS order_items (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
 product_id INTEGER REFERENCES products(id),
 product_name TEXT NOT NULL,
 price REAL NOT NULL,
 quantity INTEGER NOT NULL CHECK(quantity > 0)
);
CREATE TABLE IF NOT EXISTS cart_items (
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
 quantity INTEGER NOT NULL CHECK(quantity > 0 AND quantity <= 99),
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(user_id, product_id)
);
CREATE TABLE IF NOT EXISTS product_views (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
 product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
 viewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS payments (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
 provider_payment_id TEXT UNIQUE,
 amount REAL NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending',
 confirmation_url TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS password_reset_tokens (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, token_hash TEXT NOT NULL UNIQUE, expires_at TEXT NOT NULL, used_at TEXT);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_product_views_user ON product_views(user_id, viewed_at);
'''

SEED = [
 ('Наушники беспроводные','Электроника',3490,'Удобные беспроводные наушники для музыки, учёбы и повседневных поездок.', 'img/products/headphones.svg',12),
 ('Рюкзак городской','Аксессуары',2190,'Вместительный городской рюкзак для учёбы и работы.', 'img/products/backpack.svg',8),
 ('Настольная лампа','Для дома',1590,'Лаконичная настольная лампа для рабочего места.', 'img/products/lamp.svg',15),
 ('Клавиатура механическая','Электроника',4290,'Удобная клавиатура для работы и игр.', 'img/products/keyboard.svg',7),
 ('Керамическая кружка','Для дома',690,'Минималистичная керамическая кружка.', 'img/products/mug.svg',20),
 ('Сумка через плечо','Аксессуары',1790,'Компактная сумка на каждый день.', 'img/products/bag.svg',10),
]



def _migrate_columns(db):
    """Добавляет новые поля в существующую SQLite-базу без потери данных."""
    additions = {
        'users': {
            'phone': 'TEXT', 'company_name': "TEXT NOT NULL DEFAULT ''",
            'inn': "TEXT NOT NULL DEFAULT ''", 'seller_status': "TEXT NOT NULL DEFAULT 'approved'"
        },
        'products': {
            'moderation_status': "TEXT NOT NULL DEFAULT 'approved'",
            'is_adult': 'INTEGER NOT NULL DEFAULT 0'
        },
        'orders': {'delivery_method': "TEXT NOT NULL DEFAULT 'Курьер'"},
    }
    for table, columns in additions.items():
        existing = {row['name'] for row in db.execute(f'PRAGMA table_info({table})')}
        for name, definition in columns.items():
            if name not in existing:
                db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
    # В старой схеме email был обязательным. Пересоздаём только users, чтобы
    # поддержать регистрацию по телефону без потери ID и связанных записей.
    email_info = next((row for row in db.execute('PRAGMA table_info(users)') if row['name'] == 'email'), None)
    if email_info and email_info['notnull']:
        db.commit()
        db.execute('PRAGMA foreign_keys=OFF')
        db.execute('''CREATE TABLE users_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE,
            phone TEXT UNIQUE, password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'buyer' CHECK(role IN ('buyer','seller')),
            company_name TEXT NOT NULL DEFAULT '', inn TEXT NOT NULL DEFAULT '',
            seller_status TEXT NOT NULL DEFAULT 'approved', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        db.execute('''INSERT INTO users_new(id,name,email,phone,password_hash,role,company_name,inn,seller_status,created_at)
                      SELECT id,name,email,phone,password_hash,role,company_name,inn,seller_status,created_at FROM users''')
        db.execute('DROP TABLE users')
        db.execute('ALTER TABLE users_new RENAME TO users')
        db.commit()
        db.execute('PRAGMA foreign_keys=ON')
    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users(phone) WHERE phone IS NOT NULL AND phone <> ""')
    db.execute('CREATE INDEX IF NOT EXISTS idx_products_catalog ON products(active, moderation_status, category, created_at)')
    db.commit()


def get_db():
    if 'db' not in g:
        path = Path(current_app.config['DATABASE'])
        path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(path, timeout=20)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
        g.db.execute('PRAGMA journal_mode = WAL')
        g.db.execute('PRAGMA busy_timeout = 20000')
    return g.db


def close_db(error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    _migrate_columns(db)
    count = db.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    if count == 0:
        db.executemany(
            'INSERT INTO products(name,category,price,description,image,stock) VALUES(?,?,?,?,?,?)',
            SEED
        )
    db.commit()


def ensure_demo_user():
    db = get_db()
    email = 'seller@irsbese.demo'
    exists = db.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()
    if not exists:
        db.execute(
            'INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)',
            ('Демо-продавец', email, generate_password_hash('DemoSeller2026!'), 'seller')
        )
        db.commit()
