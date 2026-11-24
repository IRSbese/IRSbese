# ЧАСТЬ 5. Карточка товара и учёт просмотров.
from flask import Blueprint, render_template, abort, session
from app.db import get_db
from app.data import get_recommendations, save_product_view

product_bp = Blueprint('product', __name__)


@product_bp.route('/product/<int:product_id>')
def product_page(product_id):
    db = get_db()
    product = db.execute(
        '''SELECT p.*,u.name AS seller_name FROM products p
           LEFT JOIN users u ON p.seller_id=u.id
           WHERE p.id=? AND p.active=1 AND p.moderation_status='approved' AND p.is_adult=0''', (product_id,)
    ).fetchone()
    if product is None:
        abort(404)

    viewed = session.get('recently_viewed', [])
    viewed = [item for item in viewed if str(item) != str(product_id)]
    viewed.insert(0, product_id)
    session['recently_viewed'] = viewed[:20]
    save_product_view(db, product_id, session.get('user_id'))

    similar = db.execute(
        "SELECT * FROM products WHERE active=1 AND moderation_status='approved' AND is_adult=0 AND stock>0 AND category=? AND id<>? ORDER BY created_at DESC LIMIT 4",
        (product['category'], product_id)
    ).fetchall()
    often = db.execute("SELECT p.*,SUM(oi2.quantity) AS bought_together FROM order_items oi1 JOIN order_items oi2 ON oi1.order_id=oi2.order_id JOIN products p ON p.id=oi2.product_id WHERE oi1.product_id=? AND oi2.product_id<>? AND p.active=1 AND p.moderation_status='approved' AND p.is_adult=0 AND p.stock>0 GROUP BY p.id ORDER BY bought_together DESC LIMIT 6", (product_id, product_id)).fetchall()
    return render_template('pages/product.html', product=product, similar=similar, often=often)
