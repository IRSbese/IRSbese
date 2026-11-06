# ЧАСТЬ 2. Создание Flask-приложения и подключение маршрутов.

from flask import Flask
from config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Подключаем отдельные группы URL-адресов.
    from app.routes.main import main_bp
    from app.routes.catalog import catalog_bp
    from app.routes.product import product_bp
    from app.routes.cart import cart_bp
    from app.routes.account import account_bp
    from app.routes.seller import seller_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(product_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(seller_bp)

    # Общие страницы ошибок.
    @app.errorhandler(404)
    def page_not_found(error):
        from flask import render_template
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        from flask import render_template
        return render_template("500.html"), 500

    return app
