import io
import hashlib
from datetime import datetime, timedelta, timezone
from werkzeug.security import check_password_hash
import os
import re
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from app import create_app
from app.db import get_db
from app.data import get_recommendations


class MarketplaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({
            'TESTING': True,
            'SECRET_KEY': 'test-secret',
            'DATABASE': os.path.join(self.temp.name, 'test.sqlite3'),
            'UPLOAD_FOLDER': os.path.join(self.temp.name, 'uploads'),
            'SEED_DEMO_USER': False,
            'PAYMENTS_ENABLED': False,
            'DEMO_MODE': True,
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def token(self, page):
        response = self.client.get(page)
        match = re.search(rb'name="_csrf" value="([^"]+)"', response.data)
        self.assertIsNotNone(match, response.data[:1000])
        return match.group(1).decode()

    def register(self, role='buyer', email='buyer@example.test'):
        token = self.token('/register')
        return self.client.post('/register', data={
            '_csrf': token, 'name': 'Test User', 'email': email,
            'password': 'strong-pass-123', 'role': role,
            'company_name': 'Test Company' if role == 'seller' else '', 'inn': '1234567890' if role == 'seller' else ''
        }, follow_redirects=True)

    def test_home_catalog_and_product(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertIn('Content-Security-Policy', response.headers)
        self.assertEqual(self.client.get('/catalog').status_code, 200)
        self.assertEqual(self.client.get('/product/1').status_code, 200)

    def test_register_login_and_password_hash(self):
        response = self.register()
        self.assertEqual(response.status_code, 200)
        self.assertIn('История заказов'.encode(), response.data)
        with self.app.app_context():
            user = get_db().execute('SELECT password_hash FROM users WHERE email=?',
                                    ('buyer@example.test',)).fetchone()
            self.assertNotEqual(user['password_hash'], 'strong-pass-123')
        self.client.post('/logout', data={'_csrf': self.token('/account')})
        token = self.token('/login')
        response = self.client.post('/login', data={
            '_csrf': token, 'identifier': 'buyer@example.test', 'password': 'strong-pass-123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

    def test_csrf_is_required(self):
        response = self.client.post('/register', data={
            'name': 'Bad User', 'email': 'bad@example.test', 'password': 'strong-pass-123'
        })
        self.assertEqual(response.status_code, 400)

    def test_cart_is_persisted_for_account(self):
        token = self.token('/product/1')
        self.client.post('/cart/add/1', data={'_csrf': token})
        self.register(email='cart@example.test')
        with self.app.app_context():
            rows = get_db().execute('SELECT product_id,quantity FROM cart_items').fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['product_id'], 1)
            self.assertEqual(rows[0]['quantity'], 1)

    def test_order_flow(self):
        self.register(email='order@example.test')
        token = self.token('/product/1')
        self.client.post('/cart/add/1', data={'_csrf': token}, follow_redirects=True)
        self.assertEqual(self.client.get('/checkout').status_code, 200)
        token = self.token('/checkout')
        response = self.client.post('/checkout', data={
            '_csrf': token, 'name': 'Order Buyer', 'phone': '+70000000000',
            'address': 'Test street 1', 'comment': ''
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Заказ №'.encode(), response.data)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM orders').fetchone()[0], 1)
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM order_items').fetchone()[0], 1)

    def test_seller_can_add_product_and_image(self):
        self.register(role='seller', email='seller@example.test')
        token = self.token('/seller/add')
        image_buffer = io.BytesIO()
        Image.new('RGB', (24, 24), 'orange').save(image_buffer, format='PNG')
        image_buffer.seek(0)
        response = self.client.post('/seller/add', data={
            '_csrf': token, 'name': 'Test Lamp', 'category': 'Home',
            'price': '100', 'stock': '2', 'description': 'A test product',
            'image': (image_buffer, 'lamp.png')
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Test Lamp'.encode(), response.data)
        with self.app.app_context():
            product = get_db().execute("SELECT image FROM products WHERE name='Test Lamp'").fetchone()
            self.assertTrue(product['image'].endswith('.webp'))
            self.assertTrue(os.path.exists(os.path.join(self.temp.name, 'uploads', product['image'].split('/')[-1])))

    def test_buyer_cannot_open_seller_cabinet(self):
        self.register(email='buyer-role@example.test')
        self.assertEqual(self.client.get('/seller').status_code, 403)

    def test_recommendations_return_available_products(self):
        with self.app.app_context():
            recommendations = get_recommendations(get_db(), limit=3)
            self.assertEqual(len(recommendations), 3)
            self.assertTrue(all(item['stock'] > 0 for item in recommendations))


    def test_purchase_history_changes_recommendations(self):
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO users(name,email,password_hash,role) VALUES('Buyer','rec@example.test','x','buyer')")
            user_id = db.execute("SELECT id FROM users WHERE email='rec@example.test'").fetchone()['id']
            db.execute("INSERT INTO orders(user_id,total,customer_name,phone,address) VALUES(?,100,'Buyer','1','Address')", (user_id,))
            order_id = db.execute('SELECT id FROM orders WHERE user_id=?', (user_id,)).fetchone()['id']
            db.execute("INSERT INTO order_items(order_id,product_id,product_name,price,quantity) VALUES(?,?,?, ?, 1)", (order_id, 1, 'Наушники беспроводные', 3490))
            db.commit()
            recs = get_recommendations(db, user_id=user_id, limit=6)
            self.assertEqual(recs[0]['category'], 'Электроника')

    def test_registration_by_phone_and_profile_update(self):
        token = self.token('/register')
        response = self.client.post('/register', data={
            '_csrf': token, 'name': 'Phone User', 'phone': '+79990001122',
            'password': 'strong-pass-123', 'role': 'buyer'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Phone User'.encode(), response.data)
        token = self.token('/account/profile')
        response = self.client.post('/account/profile', data={
            '_csrf': token, 'name': 'Updated User', 'phone': '+79990001123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Updated User'.encode(), response.data)

    def test_seller_cannot_publish_adult_product(self):
        self.register(role='seller', email='adult-seller@example.test')
        token = self.token('/seller/add')
        response = self.client.post('/seller/add', data={
            '_csrf': token, 'name': 'Restricted item', 'category': 'Other',
            'price': '100', 'stock': '1', 'description': 'Not allowed', 'is_adult': '1'
        }, follow_redirects=True)
        self.assertIn('18+'.encode(), response.data)
        with self.app.app_context():
            count = get_db().execute("SELECT COUNT(*) FROM products WHERE name='Restricted item'").fetchone()[0]
            self.assertEqual(count, 0)

    def test_seller_can_edit_and_hide_own_product(self):
        self.register(role='seller', email='edit-seller@example.test')
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO products(seller_id,name,category,price,description,stock) VALUES(1,'Own item','Home',10,'Text',1)")
            db.commit()
            product_id = db.execute("SELECT id FROM products WHERE name='Own item'").fetchone()['id']
        token = self.token('/seller')
        response = self.client.post(f'/seller/product/{product_id}/visibility', data={'_csrf': token}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            active = get_db().execute('SELECT active FROM products WHERE id=?', (product_id,)).fetchone()['active']
            self.assertEqual(active, 0)

    def test_seller_cannot_edit_another_sellers_product(self):
        self.register(role='seller', email='owner@example.test')
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO users(name,email,password_hash,role) VALUES('Other','other@example.test','x','seller')")
            other_id = db.execute("SELECT id FROM users WHERE email='other@example.test'").fetchone()['id']
            db.execute("INSERT INTO products(seller_id,name,category,price,description) VALUES(?,'Other item','Home',10,'Text')", (other_id,))
            db.commit()
            product_id = db.execute("SELECT id FROM products WHERE name='Other item'").fetchone()['id']
        self.assertEqual(self.client.get(f'/seller/product/{product_id}/edit').status_code, 404)

    def test_bad_checkout_input_does_not_create_order(self):
        self.register(email='bad-checkout@example.test')
        token = self.token('/product/1')
        self.client.post('/cart/add/1', data={'_csrf': token})
        token = self.token('/checkout')
        response = self.client.post('/checkout', data={
            '_csrf': token, 'name': '', 'phone': '', 'address': '', 'delivery_method': 'invalid'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM orders').fetchone()[0], 0)

    def test_invalid_quantity_is_rejected(self):
        self.register(email='qty@example.test')
        token = self.token('/product/1')
        self.client.post('/cart/add/1', data={'_csrf': token})
        token = self.token('/cart')
        response = self.client.post('/cart/update', data={'_csrf': token, 'qty_1': '0'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('не меньше 1'.encode(), response.data)

    def test_phone_login(self):
        token = self.token('/register')
        self.client.post('/register', data={
            '_csrf': token, 'name': 'Phone Login', 'phone': '+79990002233',
            'password': 'strong-pass-123', 'role': 'buyer'
        })
        self.client.post('/logout', data={'_csrf': self.token('/account')})
        token = self.token('/login')
        response = self.client.post('/login', data={
            '_csrf': token, 'identifier': '+79990002233', 'password': 'strong-pass-123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Phone Login'.encode(), response.data)

    def test_payment_return_confirms_success_from_provider(self):
        self.app.config.update(PAYMENTS_ENABLED=True, YOOKASSA_SHOP_ID='test-shop', YOOKASSA_SECRET_KEY='test-secret')
        self.register(email='payment@example.test')
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO orders(user_id,total,status,customer_name,phone,address) VALUES(1,100,'Ожидает оплаты','Buyer','1','Address')")
            order_id = db.execute('SELECT id FROM orders').fetchone()['id']
            db.execute("INSERT INTO payments(order_id,provider_payment_id,amount,status,confirmation_url) VALUES(?, 'pay_test_1', 100, 'pending', 'https://pay.example.test')", (order_id,))
            db.commit()
        provider = {'id': 'pay_test_1', 'status': 'succeeded', 'amount': {'value': '100.00', 'currency': 'RUB'}, 'metadata': {'order_id': str(order_id)}}
        with patch('app.routes.payments.get_payment', return_value=provider):
            response = self.client.get(f'/payments/return?order_id={order_id}')
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            status = get_db().execute('SELECT status FROM orders WHERE id=?', (order_id,)).fetchone()['status']
            self.assertEqual(status, 'Оплачен')

    def test_canceled_webhook_is_idempotent(self):
        self.app.config.update(PAYMENTS_ENABLED=True, YOOKASSA_SHOP_ID='test-shop', YOOKASSA_SECRET_KEY='test-secret')
        self.register(email='cancel-payment@example.test')
        with self.app.app_context():
            db = get_db()
            stock_before = db.execute('SELECT stock FROM products WHERE id=1').fetchone()['stock']
            db.execute("INSERT INTO orders(user_id,total,status,customer_name,phone,address) VALUES(1,100,'Ожидает оплаты','Buyer','1','Address')")
            order_id = db.execute('SELECT id FROM orders').fetchone()['id']
            db.execute("INSERT INTO order_items(order_id,product_id,product_name,price,quantity) VALUES(?,1,'Headphones',100,1)", (order_id,))
            db.execute('UPDATE products SET stock=stock-1 WHERE id=1')
            db.execute("INSERT INTO payments(order_id,provider_payment_id,amount,status,confirmation_url) VALUES(?, 'pay_cancel_1', 100, 'pending', 'https://pay.example.test')", (order_id,))
            db.commit()
        provider = {'id': 'pay_cancel_1', 'status': 'canceled', 'amount': {'value': '100.00', 'currency': 'RUB'}, 'metadata': {'order_id': str(order_id)}}
        payload = {'event': 'payment.canceled', 'object': {'id': 'pay_cancel_1'}}
        with patch('app.routes.payments.get_payment', return_value=provider):
            self.client.post('/payments/yookassa/webhook', json=payload)
            self.client.post('/payments/yookassa/webhook', json=payload)
        with self.app.app_context():
            db = get_db()
            stock_after = db.execute('SELECT stock FROM products WHERE id=1').fetchone()['stock']
            order_status = db.execute('SELECT status FROM orders WHERE id=?', (order_id,)).fetchone()['status']
            self.assertEqual(stock_after, stock_before)
            self.assertEqual(order_status, 'Отменён')

    def test_password_reset_token_changes_password_once(self):
        self.register(email='reset@example.test')
        raw_token = 'one-time-reset-token'
        digest = hashlib.sha256(raw_token.encode()).hexdigest()
        expires = (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat()
        with self.app.app_context():
            db = get_db()
            db.execute('INSERT INTO password_reset_tokens(user_id,token_hash,expires_at) VALUES(1,?,?)', (digest, expires))
            db.commit()
        token = self.token('/reset-password/' + raw_token)
        response = self.client.post('/reset-password/' + raw_token, data={
            '_csrf': token, 'password': 'new-strong-pass-456'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            row = get_db().execute('SELECT password_hash FROM users WHERE id=1').fetchone()
            self.assertTrue(check_password_hash(row['password_hash'], 'new-strong-pass-456'))
            used = get_db().execute('SELECT used_at FROM password_reset_tokens WHERE token_hash=?', (digest,)).fetchone()['used_at']
            self.assertIsNotNone(used)

    def test_seller_can_edit_own_product(self):
        self.register(role='seller', email='edit-own@example.test')
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO products(seller_id,name,category,price,description,stock) VALUES(1,'Before','Home',10,'Text',1)")
            db.commit()
            product_id = db.execute("SELECT id FROM products WHERE name='Before'").fetchone()['id']
        token = self.token(f'/seller/product/{product_id}/edit')
        response = self.client.post(f'/seller/product/{product_id}/edit', data={
            '_csrf': token, 'name': 'After', 'category': 'Home', 'price': '20', 'stock': '4', 'description': 'Updated'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            row = get_db().execute('SELECT name,price,stock FROM products WHERE id=?', (product_id,)).fetchone()
            self.assertEqual((row['name'], row['price'], row['stock']), ('After', 20.0, 4))

    def test_stock_is_rechecked_before_order(self):
        self.register(email='stock-check@example.test')
        token = self.token('/product/1')
        self.client.post('/cart/add/1', data={'_csrf': token})
        with self.app.app_context():
            get_db().execute('UPDATE products SET stock=0 WHERE id=1')
            get_db().commit()
        token = self.token('/checkout')
        response = self.client.post('/checkout', data={
            '_csrf': token, 'name': 'Buyer', 'phone': '+79990000000', 'address': 'Address', 'delivery_method': 'Курьер'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM orders').fetchone()[0], 0)

    def test_payment_templates_do_not_collect_card_data(self):
        from pathlib import Path
        template = Path(__file__).resolve().parents[1] / 'app' / 'templates' / 'pages' / 'payment.html'
        source = template.read_text(encoding='utf-8').lower()
        self.assertNotIn('card_number', source)
        self.assertNotIn('cvv', source)
        self.assertNotIn('номер карты', source)

    def test_payment_is_disabled_by_default(self):
        self.assertEqual(self.client.get('/payments/return').status_code, 302)
        self.assertEqual(self.client.get('/payments/yookassa/webhook').status_code, 405)


if __name__ == '__main__':
    unittest.main()
