# ЧАСТЬ 5. Корзина и оформление заказа.
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from app.db import get_db
from app.helpers import cart_rows, login_required, persist_cart

cart_bp = Blueprint('cart', __name__)


@cart_bp.route('/cart')
def cart():
    rows, total = cart_rows()
    return render_template('pages/cart.html', rows=rows, total=total)


@cart_bp.route('/cart/add/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    product = get_db().execute(
        "SELECT id,stock FROM products WHERE id=? AND active=1 AND moderation_status='approved' AND is_adult=0", (product_id,)
    ).fetchone()
    if not product or product['stock'] < 1:
        flash('Товар сейчас недоступен.', 'error')
        return redirect(url_for('catalog.catalog'))
    cart = session.get('cart', {})
    key = str(product_id)
    try:
        old_quantity = int(cart.get(key, 0))
    except (TypeError, ValueError):
        old_quantity = 0
    cart[key] = min(old_quantity + 1, product['stock'], 99)
    session['cart'] = cart
    session.modified = True
    if session.get('user_id'):
        persist_cart(session['user_id'])
    flash('Товар добавлен в корзину.', 'success')
    return redirect(url_for('cart.cart'))


@cart_bp.route('/cart/update', methods=['POST'])
def update_cart():
    cart = session.get('cart', {})
    updated = {}
    invalid_quantity = False
    for key, value in request.form.items():
        if key.startswith('qty_') and key[4:].isdigit():
            product_id = int(key[4:])
            try:
                quantity = int(value)
            except ValueError:
                quantity = 0
            product = get_db().execute(
                "SELECT stock FROM products WHERE id=? AND active=1 AND moderation_status='approved' AND is_adult=0", (product_id,)
            ).fetchone()
            if quantity < 1:
                invalid_quantity = True
                continue
            if product and product['stock'] > 0:
                updated[str(product_id)] = min(quantity, product['stock'], 99)
    if invalid_quantity:
        flash('Количество товара должно быть не меньше 1. Корзина не изменена.', 'error')
        return redirect(url_for('cart.cart'))
    session['cart'] = updated
    if session.get('user_id'):
        persist_cart(session['user_id'])
    flash('Корзина обновлена.', 'success')
    return redirect(url_for('cart.cart'))


@cart_bp.route('/cart/remove/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    cart.pop(str(product_id), None)
    session['cart'] = cart
    if session.get('user_id'):
        persist_cart(session['user_id'])
    flash('Товар удалён из корзины.', 'info')
    return redirect(url_for('cart.cart'))


@cart_bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    rows, total = cart_rows()
    if not rows:
        flash('Корзина пуста.', 'info')
        return redirect(url_for('catalog.catalog'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()[:100]
        phone = request.form.get('phone', '').strip()[:40]
        address = request.form.get('address', '').strip()[:250]
        delivery_method = request.form.get('delivery_method', 'Курьер')
        comment = request.form.get('comment', '').strip()[:500]
        if not name or not phone or not address or delivery_method not in ('Курьер', 'Самовывоз'):
            form_errors = {'name': 'Укажите имя.' if not name else '', 'phone': 'Укажите телефон.' if not phone else '', 'address': 'Укажите адрес или пункт самовывоза.' if not address else '', 'delivery': 'Выберите способ доставки.' if delivery_method not in ('Курьер', 'Самовывоз') else ''}
            flash('Проверьте поля заказа.', 'error')
            return render_template('pages/checkout.html', rows=rows, total=total, form_errors=form_errors)
        db = get_db()
        try:
            db.execute('BEGIN IMMEDIATE')
            fresh_rows = []
            actual_total = 0
            for row in rows:
                product = db.execute(
                    "SELECT * FROM products WHERE id=? AND active=1 AND moderation_status='approved' AND is_adult=0", (row['product']['id'],)
                ).fetchone()
                if not product or product['stock'] < row['quantity']:
                    raise ValueError('Недостаточно товара на складе: ' + row['product']['name'])
                actual_total += round(float(product['price']) * row['quantity'], 2)
                fresh_rows.append((product, row['quantity']))
            status = 'Ожидает оплаты' if current_app.config.get('PAYMENTS_ENABLED') else 'Новый'
            cur = db.execute(
                '''INSERT INTO orders(user_id,total,status,customer_name,phone,address,delivery_method,comment)
                   VALUES(?,?,?,?,?,?,?,?)''',
                (session['user_id'], actual_total, status, name, phone, address, delivery_method, comment)
            )
            order_id = cur.lastrowid
            for product, quantity in fresh_rows:
                db.execute(
                    '''INSERT INTO order_items(order_id,product_id,product_name,price,quantity)
                       VALUES(?,?,?,?,?)''',
                    (order_id, product['id'], product['name'], product['price'], quantity)
                )
                db.execute(
                    'UPDATE products SET stock=stock-? WHERE id=?', (quantity, product['id'])
                )
            db.execute('DELETE FROM cart_items WHERE user_id=?', (session['user_id'],))
            db.commit()
        except ValueError as error:
            db.rollback()
            flash(str(error), 'error')
            return redirect(url_for('cart.cart'))
        except Exception:
            db.rollback()
            raise
        session['cart'] = {}
        session.modified = True
        if current_app.config.get('PAYMENTS_ENABLED'):
            flash(f'Заказ №{order_id} создан. Перейдите к оплате.', 'success')
            return redirect(url_for('payments.payment_page', order_id=order_id))
        flash(f'Заказ №{order_id} оформлен. Способ оплаты согласовывается отдельно.', 'success')
        return redirect(url_for('account.account'))
    return render_template('pages/checkout.html', rows=rows, total=total, form_errors={})
