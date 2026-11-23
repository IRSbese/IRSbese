# ЧАСТЬ 5. Кабинет продавца и размещение товара.
# Реальное сохранение карточек и загрузку фотографий реализовать отдельно.

from flask import Blueprint, render_template
from app.utils import login_required

seller_bp = Blueprint("seller", __name__)

@seller_bp.route("/seller")
@login_required
def seller():
    return render_template("pages/seller/index.html")

@seller_bp.route("/seller/add")
@login_required
def add_product():
    return render_template("pages/seller/add_product.html")
