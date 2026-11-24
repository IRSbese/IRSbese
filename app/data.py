# ЧАСТЬ 3. Данные каталога и персональные рекомендации.
# Все товары и история действий читаются из базы данных.


def get_product(db, product_id):
    return db.execute(
        'SELECT * FROM products WHERE id=? AND active=1', (product_id,)
    ).fetchone()


def get_recommendations(db, user_id=None, viewed_ids=None, limit=6):
    """Подбирает товары по истории покупок и просмотров.

    Покупки сильнее влияют на подбор, чем просмотры. Для нового посетителя
    используется популярность товаров по количеству заказанных единиц.
    """
    viewed_ids = viewed_ids or []
    category_score = {}

    if user_id:
        bought = db.execute(
            '''SELECT p.category, SUM(oi.quantity) AS amount
               FROM order_items oi
               JOIN orders o ON o.id=oi.order_id
               JOIN products p ON p.id=oi.product_id
               WHERE o.user_id=? AND p.category IS NOT NULL
               GROUP BY p.category''', (user_id,)
        ).fetchall()
        for row in bought:
            category_score[row['category']] = category_score.get(row['category'], 0) + int(row['amount'] or 0) * 5

        viewed = db.execute(
            '''SELECT p.category, COUNT(*) AS amount
               FROM product_views v JOIN products p ON p.id=v.product_id
               WHERE v.user_id=? GROUP BY p.category''', (user_id,)
        ).fetchall()
        for row in viewed:
            category_score[row['category']] = category_score.get(row['category'], 0) + int(row['amount'] or 0) * 2

    if viewed_ids:
        ids = [int(item) for item in viewed_ids if str(item).isdigit()]
        if ids:
            marks = ','.join('?' for _ in ids)
            rows = db.execute(
                f'SELECT category, COUNT(*) AS amount FROM products WHERE id IN ({marks}) GROUP BY category', ids
            ).fetchall()
            for row in rows:
                category_score[row['category']] = category_score.get(row['category'], 0) + int(row['amount'] or 0) * 2

    products = db.execute(
        '''SELECT p.*,
                  COALESCE((SELECT SUM(oi.quantity) FROM order_items oi
                            WHERE oi.product_id=p.id), 0) AS sold_count
           FROM products p WHERE p.active=1 AND p.moderation_status='approved' AND p.is_adult=0 AND p.stock>0'''
    ).fetchall()

    def score(product):
        return (
            category_score.get(product['category'], 0),
            int(product['sold_count'] or 0),
            product['created_at'] or ''
        )

    return sorted(products, key=score, reverse=True)[:max(1, min(int(limit), 24))]


def save_product_view(db, product_id, user_id=None):
    if user_id:
        db.execute(
            'INSERT INTO product_views(user_id, product_id) VALUES(?, ?)',
            (user_id, product_id)
        )
        db.execute(
            '''DELETE FROM product_views WHERE user_id=? AND id NOT IN
               (SELECT id FROM product_views WHERE user_id=? ORDER BY viewed_at DESC, id DESC LIMIT 200)''',
            (user_id, user_id)
        )
        db.commit()
