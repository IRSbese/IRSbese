# ЧАСТЬ 5. Главная страница маркетплейса.

from flask import Blueprint, render_template
from app.data import products

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def home():
    # Передаём несколько демонстрационных товаров в шаблон.
    return render_template("pages/home.html", products=products[:3])
