# ЧАСТЬ 1. Точка входа в приложение.
# Запускайте сайт командой: python run.py

from app import create_app

app = create_app()

if __name__ == "__main__":
    # debug=True нужен только во время разработки.
    app.run(debug=True)
