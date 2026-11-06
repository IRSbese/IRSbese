# ЧАСТЬ 5. Каталог, поиск и фильтрация товаров.

from flask import Blueprint, render_template, request
from app.data import products

catalog_bp = Blueprint("catalog", __name__)

@catalog_bp.route("/catalog")
def catalog():
    # Получаем поисковую фразу из адресной строки.
    search = request.args.get("q", "").strip().lower()
    result = products

    # Пока поиск работает по демонстрационному списку.
    if search:
        result = [item for item in products if search in item["name"].lower() or search in item["category"].lower()]

    return render_template("pages/catalog.html", products=result, search=search)
