# ЧАСТЬ 5. Главная страница и персональная подборка товаров.
from flask import Blueprint, render_template, session
from app.db import get_db
from app.data import get_recommendations

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def home():
    db = get_db()
    categories = db.execute(
        "SELECT category, COUNT(*) AS count FROM products WHERE active=1 AND moderation_status='approved' AND is_adult=0 GROUP BY category ORDER BY category"
    ).fetchall()
    products = get_recommendations(db, session.get('user_id'), session.get('recently_viewed', []), 6)
    popular = db.execute("SELECT p.*,COALESCE(SUM(oi.quantity),0) AS sold FROM products p LEFT JOIN order_items oi ON oi.product_id=p.id WHERE p.active=1 AND p.moderation_status='approved' AND p.is_adult=0 AND p.stock>0 GROUP BY p.id ORDER BY sold DESC,p.created_at DESC LIMIT 6").fetchall()
    new_products = db.execute("SELECT * FROM products WHERE active=1 AND moderation_status='approved' AND is_adult=0 AND stock>0 ORDER BY created_at DESC LIMIT 6").fetchall()
    return render_template('pages/home.html', products=products, categories=categories, popular=popular, new_products=new_products)
