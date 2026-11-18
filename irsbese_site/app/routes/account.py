# ЧАСТЬ 5. Личный кабинет покупателя.

from flask import Blueprint, render_template, session

account_bp = Blueprint("account", __name__)

@account_bp.route("/account")
def account():
    # Проверяем, вошел ли пользователь (есть ли user_id в сессии)
    if "user_id" not in session:
        # Если НЕ вошел, показываем экран с кнопками "Войти" и "Регистрация"
        # (тот самый, что на вашем скриншоте)
        return render_template("pages/account/index.html", authorized=False)
    
    # Если вошел — показываем его личный кабинет (историю заказов и имя)
    return render_template("pages/account/index.html", authorized=True, username=session.get("username"))