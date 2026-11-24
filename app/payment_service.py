# ЧАСТЬ 5. Обмен с API ЮKassa. Модуль работает только при включённом PAYMENTS_ENABLED.
import base64
import json
import urllib.error
import urllib.request
import uuid
from flask import current_app


class PaymentError(Exception):
    pass


def _request(method, path, payload=None, idempotence_key=None):
    shop_id = current_app.config['YOOKASSA_SHOP_ID']
    secret = current_app.config['YOOKASSA_SECRET_KEY']
    token = base64.b64encode(f'{shop_id}:{secret}'.encode()).decode()
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {
        'Authorization': 'Basic ' + token,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    if idempotence_key:
        headers['Idempotence-Key'] = idempotence_key
    request = urllib.request.Request(
        current_app.config['YOOKASSA_API_URL'] + path,
        data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode())
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as error:
        raise PaymentError('Не удалось связаться с ЮKassa. Попробуйте позже.') from error


def create_payment(amount, order_id, return_url):
    payload = {
        'amount': {'value': f'{float(amount):.2f}', 'currency': 'RUB'},
        'capture': True,
        'confirmation': {'type': 'redirect', 'return_url': return_url},
        'description': f'Оплата заказа IRSbese №{order_id}',
        'metadata': {'order_id': str(order_id)},
    }
    return _request('POST', '/payments', payload, str(uuid.uuid4()))


def get_payment(payment_id):
    return _request('GET', '/payments/' + payment_id)
