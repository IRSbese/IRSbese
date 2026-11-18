from flask import Blueprint, request, session, redirect, url_for, flash, render_template
from app.data import check_user_credentials, create_user

auth_bp = Blueprint("auth", __name__)

# Метод "GET", чтобы страница просто открывалась при заходе
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Получаем данные из полей формы
        login_input = request.form.get("login", "").strip()
        password = request.form.get("password", "")

        # Проверяем через Argon2
        user = check_user_credentials(login_input, password)

        if user:
            # Успех: сохраняем сессию и перенаправляем на главную
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("main.home")) 
        else:
            # Ошибка
            flash("Неверный логин или пароль", "error")
            # 3. Исправлено имя функции на 'auth.login' (а не auth.login_page)
            return redirect(url_for("auth.login")) 

    # Показываем HTML-страницу входа при GET-запросе
    return render_template("pages/account/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Простая проверка, что поля не пустые
        if not username or not email or not password:
            flash("Заполните все поля", "error")
        else:
            # Вызываем функцию из data.py (создание пользователя с Argon2)
            success = create_user(username, email, password)
            if success:
                flash("Аккаунт создан! Теперь войдите.", "success")
                return redirect(url_for("auth.login"))
            else:
                flash("Пользователь с таким именем или email уже существует", "error")

    # Показываем HTML-страницу регистрации при GET-запросе
    return render_template("pages/account/register.html")