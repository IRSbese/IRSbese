# ЧАСТЬ 2. Создание приложения, безопасность и подключение страниц.
import os
from flask import Flask, session, g, request, render_template
from config import Config
from app.db import close_db, init_db, ensure_demo_user, get_db
from app.helpers import csrf_token, check_csrf, attach_user_cart


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    if not app.config.get('TESTING'):
        # 1. Проверка SECRET_KEY
        secret = app.config.get('SECRET_KEY')
        if not secret:
            raise RuntimeError('Задайте уникальный SECRET_KEY через переменную окружения перед запуском')
        if len(secret) < 32:
            raise RuntimeError('SECRET_KEY слишком короткий. В production он должен быть не менее 32 символов.')
        if secret in ['secret', 'dev', 'change-me', 'replace-this-key-before-deployment']:
            raise RuntimeError('SECRET_KEY содержит значение по умолчанию. Сгенерируйте надежный ключ.')

        # 2. Проверка DEMO_MODE
        if app.config.get('ENVIRONMENT') == 'production' and app.config.get('DEMO_MODE'):
            raise RuntimeError('DEMO_MODE включен. В production демо-режим должен быть отключен (DEMO_MODE=0).')

        # 3. Проверка DEBUG
        if app.config.get('ENVIRONMENT') == 'production' and app.config.get('DEBUG'):
            raise RuntimeError('DEBUG включен. В production отладка должна быть отключена (FLASK_DEBUG=0).')

        # 4. Проверка Cookie Secure
        if app.config.get('ENVIRONMENT') == 'production' and not app.config.get('SESSION_COOKIE_SECURE'):
            raise RuntimeError('SESSION_COOKIE_SECURE выключен. В production требуется HTTPS и COOKIE_SECURE=1.')

    # Проверка оплаты (оставляем как было)
    if app.config.get('PAYMENTS_ENABLED') and not (
        app.config.get('YOOKASSA_SHOP_ID') and app.config.get('YOOKASSA_SECRET_KEY')
    ):
        raise RuntimeError('Для включения оплаты задайте YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY')

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.teardown_appcontext(close_db)

    from app.routes.main import main_bp
    from app.routes.catalog import catalog_bp
    from app.routes.product import product_bp
    from app.routes.cart import cart_bp
    from app.routes.account import account_bp
    from app.routes.seller import seller_bp
    from app.routes.payments import payments_bp
    for blueprint in (main_bp, catalog_bp, product_bp, cart_bp, account_bp, seller_bp, payments_bp):
        app.register_blueprint(blueprint)

    @app.before_request
    def prepare_request():
        if not isinstance(session.get('cart'), dict):
            session['cart'] = {}
        g.user = None
        if session.get('user_id'):
            session.permanent = True
            g.user = get_db().execute(
                'SELECT id,name,email,role FROM users WHERE id=?', (session['user_id'],)
            ).fetchone()
            if g.user is None:
                session.clear()
                session['cart'] = {}
            elif session.get('cart_user_id') != g.user['id']:
                attach_user_cart(g.user['id'])

        # Защита всех изменяющих запросов. Webhook подтверждается запросом к ЮKassa.
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and request.endpoint != 'payments.yookassa_webhook':
            check_csrf()

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'self'; "
            "img-src 'self' data:; style-src 'self' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; form-action 'self'"
        )
        if request.path.startswith(('/account', '/cart', '/checkout', '/seller')):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.context_processor
    def common_values():
        cart = session.get('cart', {})
        count = sum(int(value) for value in cart.values() if str(value).isdigit())
        return {
            'cart_count': count,
            'current_user': getattr(g, 'user', None),
            'csrf_token': csrf_token,
            'payments_enabled': bool(app.config.get('PAYMENTS_ENABLED')),
        }

    @app.errorhandler(400)
    def bad_request(error):
        return render_template('400.html'), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template('403.html'), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template('404.html'), 404

    @app.errorhandler(413)
    def too_large(error):
        return render_template('413.html'), 413

    @app.errorhandler(500)
    def server_error(error):
        return render_template('500.html'), 500

    with app.app_context():
        init_db()
        if app.config.get('SEED_DEMO_USER', app.config.get('DEMO_MODE', False)):
            ensure_demo_user()
    return app
