# ЧАСТЬ 5. Главная страница маркетплейса.

from flask import Blueprint, render_template
from app.data import get_products

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def home():
    # Передаём несколько демонстрационных товаров в шаблон.
    all_products = get_products()
    return render_template("pages/home.html", products=all_products[:3])
