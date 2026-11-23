# ЧАСТЬ 5. Личный кабинет покупателя.

from flask import Blueprint, render_template, session
from app.data import get_user_orders
from app.utils import login_required

account_bp = Blueprint("account", __name__)

@account_bp.route("/account")
@login_required
def account():
    orders = get_user_orders(session["user_id"])
    return render_template("pages/account/index.html", authorized=True, username=session.get("username"),orders=orders)