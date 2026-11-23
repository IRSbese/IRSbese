# ЧАСТЬ 5. Корзина и оформление заказа.

from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from app.data import add_to_cart, get_cart_items, remove_from_cart, create_order, increase_cart_item, decrease_cart_item
from app.utils import login_required

cart_bp = Blueprint("cart", __name__)

@cart_bp.route("/cart")
@login_required
def cart():
    # Получаем товары из БД для текущего пользователя
    items = get_cart_items(session["user_id"])
    
    # Считаем общую сумму (цена * количество)
    total = sum(item["price"] * item["quantity"] for item in items)
    
    return render_template("pages/cart.html", items=items, total=total)

@cart_bp.route("/cart/add/<int:product_id>")
@login_required
def add(product_id):
    # Добавляем товар в корзину в базе данных
    add_to_cart(session["user_id"], product_id)
    flash("Товар добавлен в корзину!", "success")
    
    # Возвращаем пользователя обратно на страницу товара
    return redirect(request.referrer or url_for("catalog.catalog"))

@cart_bp.route("/cart/remove/<int:cart_id>")
@login_required
def remove(cart_id):
    remove_from_cart(cart_id)
    return redirect(url_for("cart.cart"))

@cart_bp.route("/cart/increase/<int:cart_id>")
@login_required
def increase(cart_id):
    increase_cart_item(cart_id)
    return redirect(url_for("cart.cart"))

@cart_bp.route("/cart/decrease/<int:cart_id>")
@login_required
def decrease(cart_id):
    decrease_cart_item(cart_id)
    return redirect(url_for("cart.cart"))

@cart_bp.route("/checkout")
@login_required
def checkout():
    # Переносим товары из корзины в заказ и очищаем корзину
    order_id = create_order(session["user_id"])
    
    if order_id:
        flash(f"Заказ №{order_id} успешно оформлен!", "success")
        # Отправляем в личный кабинет смотреть историю заказов
        return redirect(url_for("account.account"))
    else:
        flash("Ваша корзина пуста, нечего оформлять.", "error")
        return redirect(url_for("cart.cart"))