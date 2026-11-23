# ЧАСТЬ 5. Каталог, поиск и фильтрация товаров.

from flask import Blueprint, render_template, request
from app.data import search_products

catalog_bp = Blueprint("catalog", __name__)

@catalog_bp.route("/catalog")
def catalog():
    # Получаем поисковую фразу из адресной строки.
    search_query = request.args.get("q", "").strip()
    result = search_products(search_query)
    return render_template("pages/catalog.html", products=result, search_query=search_query)
