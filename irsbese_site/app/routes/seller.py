# ЧАСТЬ 5. Кабинет продавца и размещение товара.
# Реальное сохранение карточек и загрузку фотографий реализовать отдельно.

from flask import Blueprint, render_template

seller_bp = Blueprint("seller", __name__)

@seller_bp.route("/seller")
def seller():
    return render_template("pages/seller/index.html")

@seller_bp.route("/seller/add")
def add_product():
    return render_template("pages/seller/add_product.html")
