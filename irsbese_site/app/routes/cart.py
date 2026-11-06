# ЧАСТЬ 5. Корзина и оформление заказа.
# Здесь пока только интерфейс. Сохранение корзины и заказов добавит разработчик.

from flask import Blueprint, render_template

cart_bp = Blueprint("cart", __name__)

@cart_bp.route("/cart")
def cart():
    return render_template("pages/cart.html")

@cart_bp.route("/checkout")
def checkout():
    return render_template("pages/checkout.html")
