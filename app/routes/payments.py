# ЧАСТЬ 5. Создание платежа и подтверждение статуса через API ЮKassa.
import re
from flask import Blueprint, current_app, abort, request, jsonify, redirect, url_for, flash, session, render_template
from app.db import get_db
from app.helpers import login_required
from app.payment_service import create_payment as yookassa_create, get_payment, PaymentError

payments_bp = Blueprint('payments', __name__)


def payments_are_ready():
    return bool(
        current_app.config.get('PAYMENTS_ENABLED')
        and current_app.config.get('YOOKASSA_SHOP_ID')
        and current_app.config.get('YOOKASSA_SECRET_KEY')
    )


@payments_bp.route('/payments/continue/<int:order_id>')
@login_required
def payment_page(order_id):
    if not payments_are_ready():
        flash('Онлайн-оплата пока не включена.', 'info')
        return redirect(url_for('account.account'))
    db = get_db()
    order = db.execute(
        'SELECT * FROM orders WHERE id=? AND user_id=?', (order_id, session['user_id'])
    ).fetchone()
    if not order:
        abort(404)
    if order['status'] != 'Ожидает оплаты':
        abort(400)
    payment = db.execute('SELECT * FROM payments WHERE order_id=?', (order_id,)).fetchone()
    if payment and payment['status'] == 'succeeded':
        flash('Этот заказ уже оплачен.', 'success')
        return redirect(url_for('account.account'))
    if payment and payment['confirmation_url'] and payment['status'] not in ('succeeded', 'canceled'):
        return redirect(payment['confirmation_url'])
    return render_template('pages/payment.html', order=order)


@payments_bp.route('/payments/create/<int:order_id>', methods=['POST'])
@login_required
def create_payment(order_id):
    if not payments_are_ready():
        flash('Онлайн-оплата пока не включена.', 'info')
        return redirect(url_for('account.account'))
    db = get_db()
    order = db.execute(
        'SELECT * FROM orders WHERE id=? AND user_id=?', (order_id, session['user_id'])
    ).fetchone()
    if not order:
        abort(404)
    if order['status'] != 'Ожидает оплаты':
        abort(400)
    payment = db.execute('SELECT * FROM payments WHERE order_id=?', (order_id,)).fetchone()
    if payment and payment['status'] == 'succeeded':
        flash('Этот заказ уже оплачен.', 'success')
        return redirect(url_for('account.account'))
    if payment and payment['confirmation_url'] and payment['status'] not in ('succeeded', 'canceled'):
        return redirect(payment['confirmation_url'])
    try:
        result = yookassa_create(
            order['total'], order_id,
            url_for('payments.payment_return', order_id=order_id, _external=True)
        )
        confirmation_url = result.get('confirmation', {}).get('confirmation_url', '')
        if not result.get('id') or not confirmation_url.startswith('https://'):
            raise PaymentError('ЮKassa не вернула ссылку на оплату.')
        db.execute(
            '''INSERT INTO payments(order_id,provider_payment_id,amount,status,confirmation_url)
               VALUES(?,?,?,?,?)
               ON CONFLICT(order_id) DO UPDATE SET
               provider_payment_id=excluded.provider_payment_id,
               amount=excluded.amount,status=excluded.status,
               confirmation_url=excluded.confirmation_url,updated_at=CURRENT_TIMESTAMP''',
            (order_id, result['id'], order['total'], result.get('status', 'pending'), confirmation_url)
        )
        db.commit()
        return redirect(confirmation_url)
    except PaymentError as error:
        flash(str(error), 'error')
        return redirect(url_for('account.account'))


@payments_bp.route('/payments/return')
@login_required
def payment_return():
    order_id = request.args.get('order_id', type=int)
    if not order_id:
        flash('Возврат со страницы оплаты получен. Проверяем статус в личном кабинете.', 'info')
        return redirect(url_for('account.account'))
    db = get_db()
    order = db.execute('SELECT * FROM orders WHERE id=? AND user_id=?', (order_id, session['user_id'])).fetchone()
    if not order:
        abort(404)
    payment = db.execute('SELECT * FROM payments WHERE order_id=?', (order_id,)).fetchone()
    state = 'pending'
    if payment and payment['provider_payment_id'] and payments_are_ready():
        try:
            confirmed = get_payment(payment['provider_payment_id'])
            amount = (confirmed.get('amount') or {}).get('value')
            currency = (confirmed.get('amount') or {}).get('currency')
            metadata_order = str((confirmed.get('metadata') or {}).get('order_id', ''))
            if confirmed.get('id') == payment['provider_payment_id'] and currency == 'RUB' and amount and abs(float(amount) - float(payment['amount'])) <= 0.01 and metadata_order == str(order_id):
                state = confirmed.get('status', 'pending')
                _apply_payment_state(db, payment, order, state)
        except (PaymentError, TypeError, ValueError):
            current_app.logger.warning('Не удалось обновить статус платежа для заказа %s', order_id)
    if state == 'succeeded':
        message = 'Оплата подтверждена. Заказ оплачен.'
    elif state == 'canceled':
        message = 'Платёж отклонён или отменён. Заказ отменён.'
    else:
        message = 'Платёж ожидает подтверждения. Статус обновится после ответа ЮKassa.'
    return render_template('pages/payment_result.html', order=order, payment_state=state, message=message)


def _apply_payment_state(db, payment, order, provider_status):
    if provider_status == 'succeeded':
        # 1. Проверяем, не отменён ли заказ. Если отменён — игнорируем оплату.
        current_order = db.execute('SELECT status FROM orders WHERE id=?', (order['id'],)).fetchone()
        if current_order and current_order['status'] == 'Отменён':
            current_app.logger.warning(f'Попытка оплаты отмененного заказа {order["id"]} проигнорирована.')
            return

        # Обновляем статус платежа и заказа
        db.execute("UPDATE payments SET status='succeeded',updated_at=CURRENT_TIMESTAMP WHERE id=?", (payment['id'],))
        # Обновляем статус только если он ещё не "Оплачен"
        db.execute("UPDATE orders SET status='Оплачен' WHERE id=? AND status<>'Оплачен'", (order['id'],))
        db.commit()

    elif provider_status == 'canceled':
        # 2. Начинаем транзакцию для безопасного возврата остатков
        db.execute('BEGIN IMMEDIATE')
        try:
            # Снова получаем актуальный статус заказа ВНУТРИ транзакции (защита от гонок)
            current_order = db.execute('SELECT status FROM orders WHERE id=?', (order['id'],)).fetchone()
            
            # Если заказ уже отменён или оплачен — ничего не делаем (возврат сработает только 1 раз)
            if not current_order or current_order['status'] in ('Отменён', 'Оплачен'):
                db.rollback()
                return

            # Возвращаем товары на склад
            items = db.execute('SELECT product_id,quantity FROM order_items WHERE order_id=?', (order['id'],)).fetchall()
            for item in items:
                if item['product_id']:
                    db.execute('UPDATE products SET stock=stock+? WHERE id=?', (item['quantity'], item['product_id']))
            
            # Меняем статусы
            db.execute("UPDATE payments SET status='canceled',updated_at=CURRENT_TIMESTAMP WHERE id=?", (payment['id'],))
            db.execute("UPDATE orders SET status='Отменён' WHERE id=?", (order['id'],))
            db.commit()
        except Exception:
            db.rollback()
            raise

    elif provider_status == 'pending':
        db.execute("UPDATE payments SET status='pending',updated_at=CURRENT_TIMESTAMP WHERE id=?", (payment['id'],))
        db.commit()

@payments_bp.route('/payments/yookassa/webhook', methods=['POST'])
def yookassa_webhook():
    if not payments_are_ready():
        abort(404)
    payload = request.get_json(silent=True) or {}
    event = payload.get('event', '')
    payment_object = payload.get('object') or {}
    payment_id = payment_object.get('id')
    if event not in ('payment.succeeded', 'payment.canceled') or not payment_id:
        return jsonify({'ok': True})
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', str(payment_id)):
        return jsonify({'ok': False}), 400
    try:
        confirmed = get_payment(payment_id)
    except PaymentError:
        return jsonify({'ok': False}), 503
    db = get_db()
    local = db.execute('SELECT * FROM payments WHERE provider_payment_id=?', (payment_id,)).fetchone()
    if not local:
        return jsonify({'ok': True})
    order = db.execute('SELECT * FROM orders WHERE id=?', (local['order_id'],)).fetchone()
    if not order:
        return jsonify({'ok': True})
    provider_status = confirmed.get('status')
    provider_amount = (confirmed.get('amount') or {}).get('value')
    provider_currency = (confirmed.get('amount') or {}).get('currency')
    metadata_order = str((confirmed.get('metadata') or {}).get('order_id', ''))
    if confirmed.get('id') != payment_id or provider_currency != 'RUB' or not provider_amount or abs(float(provider_amount) - float(local['amount'])) > 0.01 or metadata_order != str(local['order_id']):
        return jsonify({'ok': False}), 400
    if provider_status == 'succeeded' and event == 'payment.succeeded':
        _apply_payment_state(db, local, order, provider_status)
    elif provider_status == 'canceled' and event == 'payment.canceled':
        _apply_payment_state(db, local, order, provider_status)
    return jsonify({'ok': True})
