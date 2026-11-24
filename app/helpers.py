# Общие функции: CSRF, права доступа и работа с корзиной.
import secrets
from functools import wraps
from flask import session, redirect, url_for, flash, request, abort
from app.db import get_db


def csrf_token():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_urlsafe(32)
    return session['_csrf']


def check_csrf():
    token = request.form.get('_csrf', '')
    if not token or not secrets.compare_digest(token, session.get('_csrf', '')):
        abort(400, 'Недействительный запрос. Обновите страницу и повторите попытку.')


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('user_id'):
            flash('Войдите в аккаунт, чтобы продолжить.', 'info')
            return redirect(url_for('account.login', next=request.path))
        return view(*args, **kwargs)
    return wrapped


def seller_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('user_id'):
            flash('Сначала войдите в аккаунт.', 'info')
            return redirect(url_for('account.login'))
        user = get_db().execute('SELECT role FROM users WHERE id=?', (session['user_id'],)).fetchone()
        if not user or user['role'] != 'seller':
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def _clean_cart(cart):
    result = {}
    if not isinstance(cart, dict):
        return result
    for key, value in cart.items():
        if str(key).isdigit():
            try:
                qty = int(value)
            except (TypeError, ValueError):
                continue
            if qty > 0:
                result[str(int(key))] = min(qty, 99)
    return result


def persist_cart(user_id=None):
    user_id = user_id or session.get('user_id')
    if not user_id:
        return
    db = get_db()
    cart = _clean_cart(session.get('cart', {}))
    db.execute('DELETE FROM cart_items WHERE user_id=?', (user_id,))
    for product_id, quantity in cart.items():
        product = db.execute(
            "SELECT stock FROM products WHERE id=? AND active=1 AND moderation_status='approved' AND is_adult=0", (int(product_id),)
        ).fetchone()
        if product and product['stock'] > 0:
            db.execute(
                'INSERT INTO cart_items(user_id,product_id,quantity) VALUES(?,?,?)',
                (user_id, int(product_id), min(quantity, product['stock'], 99))
            )
    db.commit()
    session['cart'] = cart


def attach_user_cart(user_id, current_cart=None):
    """Объединяет гостевую корзину с сохранённой корзиной аккаунта."""
    db = get_db()
    merged = _clean_cart(current_cart if current_cart is not None else session.get('cart', {}))
    saved = db.execute(
        'SELECT product_id, quantity FROM cart_items WHERE user_id=?', (user_id,)
    ).fetchall()
    for row in saved:
        key = str(row['product_id'])
        merged[key] = min(99, merged.get(key, 0) + row['quantity'])
    session['cart'] = merged
    session['cart_user_id'] = user_id
    persist_cart(user_id)


def cart_rows():
    cart = _clean_cart(session.get('cart', {}))
    if not cart:
        return [], 0
    ids = [int(key) for key in cart]
    marks = ','.join('?' for _ in ids)
    products = get_db().execute(
        f"SELECT * FROM products WHERE active=1 AND moderation_status='approved' AND is_adult=0 AND id IN ({marks})", ids
    ).fetchall()
    rows, total, fixed_cart = [], 0, {}
    for product in products:
        # Ограничиваем количество остатком на складе (и максимум 99)
        raw_qty = cart.get(str(product['id']), 0)
        if product['stock'] > 0:
            quantity = min(raw_qty, product['stock'], 99)
        else:
            quantity = 0 # Если на складе 0, товар в корзине не показываем

        if quantity <= 0:
            continue
            
        line_total = round(float(product['price']) * quantity, 2)
        rows.append({'product': product, 'quantity': quantity, 'line_total': line_total})
        fixed_cart[str(product['id'])] = quantity
        total += line_total
    return rows, round(total, 2)
