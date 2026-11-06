# ЧАСТЬ 5. Страница отдельного товара.

from flask import Blueprint, render_template, abort
from app.data import get_product

product_bp = Blueprint("product", __name__)

@product_bp.route("/product/<int:product_id>")
def product_page(product_id):
    # Если товара с таким ID нет, показываем ошибку 404.
    product = get_product(product_id)
    if product is None:
        abort(404)
    return render_template("pages/product.html", product=product)
