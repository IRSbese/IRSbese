import sqlite3

# Подключаемся к базе (убедитесь, что путь к файлу правильный)
conn = sqlite3.connect("products.db")

# Получаем всех пользователей
users = conn.execute("SELECT * FROM users").fetchall()

# Выводим на экран
print("--- СПИСОК ПОЛЬЗОВАТЕЛЕЙ ---")
for user in users:
    print(user)

conn.close()