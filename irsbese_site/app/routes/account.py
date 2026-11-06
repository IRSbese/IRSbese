# ЧАСТЬ 5. Личный кабинет покупателя.
# Регистрацию, авторизацию и историю заказов подключить к базе данных позже.

from flask import Blueprint, render_template

account_bp = Blueprint("account", __name__)

@account_bp.route("/account")
def account():
    return render_template("pages/account/index.html")

@account_bp.route("/login")
def login():
    return render_template("pages/account/login.html")

@account_bp.route("/register")
def register():
    return render_template("pages/account/register.html")
