# ЧАСТЬ 5. Каталог, поиск, фильтры и сортировка.
from flask import Blueprint, render_template, request
from app.db import get_db

catalog_bp = Blueprint('catalog', __name__)


@catalog_bp.route('/catalog')
def catalog():
    search = request.args.get('q', '').strip()[:100]
    category = request.args.get('category', '').strip()[:60]
    sort = request.args.get('sort', 'new')
    order = {
        'price_up': 'price ASC',
        'price_down': 'price DESC',
        'name': 'name COLLATE NOCASE ASC',
        'new': 'created_at DESC',
    }.get(sort, 'created_at DESC')
    sql = "SELECT * FROM products WHERE active=1 AND moderation_status='approved' AND is_adult=0"
    args = []
    if search:
        sql += ' AND (name LIKE ? OR description LIKE ? OR category LIKE ?)'
        args += [f'%{search}%', f'%{search}%', f'%{search}%']
    if category:
        sql += ' AND category=?'
        args.append(category)
    products = get_db().execute(sql + ' ORDER BY ' + order, args).fetchall()
    categories = get_db().execute(
        "SELECT DISTINCT category FROM products WHERE active=1 AND moderation_status='approved' AND is_adult=0 ORDER BY category"
    ).fetchall()
    return render_template(
        'pages/catalog.html', products=products, search=search,
        category=category, categories=categories, sort=sort
    )
