# ЧАСТЬ 5. Регистрация, вход, профиль, история заказов и восстановление доступа.
import hashlib
import re
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from app.db import get_db
from app.helpers import login_required, attach_user_cart

account_bp = Blueprint('account', __name__)
EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
PHONE_RE = re.compile(r'^\+?[0-9 ()-]{10,20}$')


def _send_reset_email(email, link):
    host = current_app.config.get('SMTP_HOST')
    if not host:
        return False
    message = EmailMessage()
    message['Subject'] = 'Восстановление доступа IRSbese'
    message['From'] = current_app.config.get('SMTP_FROM', 'noreply@irsbese.local')
    message['To'] = email
    message.set_content('Для смены пароля откройте ссылку (действует 30 минут): ' + link)
    with smtplib.SMTP(host, int(current_app.config.get('SMTP_PORT', 587)), timeout=10) as smtp:
        smtp.starttls()
        username = current_app.config.get('SMTP_USER')
        if username:
            smtp.login(username, current_app.config.get('SMTP_PASSWORD', ''))
        smtp.send_message(message)
    return True


@account_bp.route('/account')
@login_required
def account():
    db = get_db()
    user = db.execute('SELECT id,name,email,phone,role,company_name,inn,created_at FROM users WHERE id=?', (session['user_id'],)).fetchone()
    orders = db.execute('SELECT * FROM orders WHERE user_id=? ORDER BY id DESC', (session['user_id'],)).fetchall()
    items = {order['id']: db.execute('SELECT * FROM order_items WHERE order_id=?', (order['id'],)).fetchall() for order in orders}
    payments = {row['order_id']: row for row in db.execute('SELECT * FROM payments WHERE order_id IN (SELECT id FROM orders WHERE user_id=?)', (session['user_id'],)).fetchall()}
    return render_template('pages/account/index.html', user=user, orders=orders, items=items, payments=payments)


@account_bp.route('/account/profile', methods=['GET', 'POST'])
@login_required
def profile():
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()[:80]
        phone = request.form.get('phone', '').strip()[:30]
        if len(name) < 2 or (phone and not PHONE_RE.match(phone)):
            flash('Проверьте имя и номер телефона.', 'error')
        else:
            try:
                db.execute('UPDATE users SET name=?,phone=? WHERE id=?', (name, phone or None, session['user_id']))
                db.commit()
                flash('Профиль обновлён.', 'success')
                return redirect(url_for('account.account'))
            except Exception as error:
                db.rollback()
                if 'UNIQUE' in str(error).upper():
                    flash('Этот номер уже используется.', 'error')
                else:
                    raise
    return render_template('pages/account/profile.html', user=user)


@account_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()[:80]
        email = request.form.get('email', '').strip().lower()[:150] or None
        phone = request.form.get('phone', '').strip()[:30] or None
        password = request.form.get('password', '')
        role = request.form.get('role', 'buyer')
        company = request.form.get('company_name', '').strip()[:160]
        inn = re.sub(r'\D', '', request.form.get('inn', ''))[:12]
        valid_contact = bool((email and EMAIL_RE.match(email)) or (phone and PHONE_RE.match(phone)))
        valid_seller = role != 'seller' or (len(company) >= 2 and len(inn) in (10, 12))
        if role not in ('buyer', 'seller') or len(name) < 2 or not valid_contact or len(password) < 8 or not valid_seller:
            form_errors = {}
            if len(name) < 2: form_errors['name'] = 'Введите имя не короче 2 символов.'
            if not valid_contact: form_errors['contact'] = 'Укажите корректную почту или телефон.'
            if len(password) < 8: form_errors['password'] = 'Пароль должен содержать минимум 8 символов.'
            if not valid_seller: form_errors['company'] = 'Для продавца нужны название компании и ИНН из 10 или 12 цифр.'
            flash('Проверьте поля формы.', 'error')
            return render_template('pages/account/register.html', form_errors=form_errors)
        else:
            db = get_db()
            try:
                cur = db.execute('INSERT INTO users(name,email,phone,password_hash,role,company_name,inn) VALUES(?,?,?,?,?,?,?)',
                    (name, email, phone, generate_password_hash(password), role, company if role == 'seller' else '', inn if role == 'seller' else ''))
                db.commit()
                guest_cart = session.get('cart', {})
                session.clear()
                session['user_id'] = cur.lastrowid
                attach_user_cart(cur.lastrowid, guest_cart)
                flash('Аккаунт создан. Добро пожаловать!', 'success')
                return redirect(url_for('account.account'))
            except Exception as error:
                db.rollback()
                if 'UNIQUE' in str(error).upper():
                    flash('Такая почта или телефон уже зарегистрированы.', 'error')
                else:
                    raise
    return render_template('pages/account/register.html', form_errors={})


@account_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip().lower()
        password = request.form.get('password', '')
        user = get_db().execute('SELECT * FROM users WHERE lower(email)=? OR phone=?', (identifier, identifier)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            guest_cart = session.get('cart', {})
            session.clear()
            session['user_id'] = user['id']
            attach_user_cart(user['id'], guest_cart)
            flash('Вы вошли в аккаунт.', 'success')
            target = request.args.get('next', '')
            return redirect(target if target.startswith('/') and not target.startswith('//') else url_for('account.account'))
        flash('Неверная почта, телефон или пароль.', 'error')
        return render_template('pages/account/login.html', login_error='Проверьте почту/телефон и пароль.')
    return render_template('pages/account/login.html', login_error='')


@account_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip().lower()
        user = get_db().execute('SELECT * FROM users WHERE lower(email)=? OR phone=?', (identifier, identifier)).fetchone()
        # Не раскрываем, существует ли аккаунт. Отправка доступна при настроенном SMTP и наличии email.
        if user and user['email'] and current_app.config.get('SMTP_HOST'):
            raw = secrets.token_urlsafe(32)
            digest = hashlib.sha256(raw.encode()).hexdigest()
            expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
            db = get_db()
            db.execute('INSERT INTO password_reset_tokens(user_id,token_hash,expires_at) VALUES(?,?,?)', (user['id'], digest, expires))
            db.commit()
            link = url_for('account.reset_password', token=raw, _external=True)
            try:
                _send_reset_email(user['email'], link)
            except Exception:
                current_app.logger.exception('Не удалось отправить письмо восстановления')
        flash('Если аккаунт найден и почта доступна, инструкция отправлена.', 'info')
        return redirect(url_for('account.login'))
    return render_template('pages/account/forgot_password.html')


@account_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    digest = hashlib.sha256(token.encode()).hexdigest()
    row = get_db().execute('SELECT * FROM password_reset_tokens WHERE token_hash=? AND used_at IS NULL', (digest,)).fetchone()
    if not row or datetime.fromisoformat(row['expires_at']) < datetime.now(timezone.utc):
        flash('Ссылка недействительна или устарела.', 'error')
        return redirect(url_for('account.forgot_password'))
    if request.method == 'POST':
        password = request.form.get('password', '')
        if len(password) < 8:
            flash('Пароль должен содержать минимум 8 символов.', 'error')
        else:
            db = get_db()
            db.execute('UPDATE users SET password_hash=? WHERE id=?', (generate_password_hash(password), row['user_id']))
            db.execute('UPDATE password_reset_tokens SET used_at=CURRENT_TIMESTAMP WHERE id=?', (row['id'],))
            db.commit()
            flash('Пароль изменён. Теперь войдите.', 'success')
            return redirect(url_for('account.login'))
    return render_template('pages/account/reset_password.html')


@account_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('Вы вышли из аккаунта.', 'info')
    return redirect(url_for('main.home'))
