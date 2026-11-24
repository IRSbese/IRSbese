# ЧАСТЬ 5. Кабинет продавца, управление товарами и безопасная загрузка фотографий.
from pathlib import Path
import math
import uuid
from PIL import Image, ImageOps, UnidentifiedImageError
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, abort
from app.db import get_db
from app.helpers import seller_required

seller_bp = Blueprint('seller', __name__)
ADULT_MARKERS = ('18+', '18 +', 'для взрослых', 'эрот', 'интим', 'секс-товар', 'секс товар')

def is_adult_product(name, category, description, checked=False):
    text = ' '.join((name, category, description)).casefold()
    return checked or any(marker in text for marker in ADULT_MARKERS)


def save_product_image(file):
    if not file or not file.filename:
        return ''
    try:
        image = Image.open(file.stream)
        if image.format not in ('JPEG', 'PNG', 'WEBP'):
            raise ValueError('Поддерживаются только JPG, PNG и WEBP.')
        image = ImageOps.exif_transpose(image)
        image.thumbnail((1800, 1800))
        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGBA' if 'A' in image.getbands() else 'RGB')
        folder = Path(current_app.config['UPLOAD_FOLDER'])
        folder.mkdir(parents=True, exist_ok=True)
        filename = uuid.uuid4().hex + '.webp'
        image.save(folder / filename, 'WEBP', quality=86, method=6)
        return 'uploads/' + filename
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError):
        raise ValueError('Файл не является корректным изображением.')


@seller_bp.route('/seller')
@seller_required
def seller():
    products = get_db().execute('SELECT * FROM products WHERE seller_id=? ORDER BY id DESC', (session['user_id'],)).fetchall()
    return render_template('pages/seller/index.html', products=products)


@seller_bp.route('/seller/add', methods=['GET', 'POST'])
@seller_required
def add_product():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()[:120]
        category = request.form.get('category', '').strip()[:60]
        description = request.form.get('description', '').strip()[:1500]
        is_adult = is_adult_product(name, category, description, request.form.get('is_adult') == '1')
        try:
            price = round(float(request.form.get('price', '0')), 2)
            stock = int(request.form.get('stock', '1'))
        except ValueError:
            price, stock = -1, 0
        if is_adult:
            flash('Размещение товаров категории 18+ запрещено правилами IRSbese.', 'error')
            return render_template('pages/seller/add_product.html', form_errors={'adult': 'Товары 18+ запрещены.'})
        if len(name) < 2 or not category or not description or not math.isfinite(price) or price <= 0 or stock < 0 or stock > 10000:
            flash('Проверьте название, категорию, описание, цену и остаток.', 'error')
            return render_template('pages/seller/add_product.html', form_errors={'product': 'Название, категория, описание, цена или остаток заполнены неверно.'})
        try:
            image_path = save_product_image(request.files.get('image'))
        except ValueError as error:
            flash(str(error), 'error')
            return render_template('pages/seller/add_product.html', form_errors={'image': str(error)})
        db = get_db()
        db.execute('INSERT INTO products(seller_id,name,category,price,description,image,stock,is_adult,moderation_status) VALUES(?,?,?,?,?,?,?,?,?)',
            (session['user_id'], name, category, price, description, image_path, stock, 0, 'approved'))
        db.commit()
        flash('Товар опубликован в каталоге.', 'success')
        return redirect(url_for('seller.seller'))
    return render_template('pages/seller/add_product.html', form_errors={})


@seller_bp.route('/seller/product/<int:product_id>/edit', methods=['GET', 'POST'])
@seller_required
def edit_product(product_id):
    db = get_db()
    product = db.execute('SELECT * FROM products WHERE id=? AND seller_id=?', (product_id, session['user_id'])).fetchone()
    if not product:
        abort(404)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()[:120]
        category = request.form.get('category', '').strip()[:60]
        description = request.form.get('description', '').strip()[:1500]
        try:
            price = round(float(request.form.get('price', '0')), 2)
            stock = int(request.form.get('stock', '0'))
        except ValueError:
            price, stock = -1, -1
        if len(name) < 2 or not category or not description or not math.isfinite(price) or price <= 0 or not 0 <= stock <= 10000:
            flash('Проверьте поля товара.', 'error')
        else:
            db.execute('UPDATE products SET name=?,category=?,description=?,price=?,stock=? WHERE id=? AND seller_id=?',
                (name, category, description, price, stock, product_id, session['user_id']))
            db.commit()
            flash('Товар обновлён.', 'success')
            return redirect(url_for('seller.seller'))
    return render_template('pages/seller/edit_product.html', product=product)


@seller_bp.route('/seller/product/<int:product_id>/visibility', methods=['POST'])
@seller_required
def toggle_product(product_id):
    db = get_db()
    product = db.execute('SELECT active FROM products WHERE id=? AND seller_id=?', (product_id, session['user_id'])).fetchone()
    if not product:
        abort(404)
    db.execute('UPDATE products SET active=? WHERE id=? AND seller_id=?', (0 if product['active'] else 1, product_id, session['user_id']))
    db.commit()
    flash('Статус товара изменён.', 'success')
    return redirect(url_for('seller.seller'))
