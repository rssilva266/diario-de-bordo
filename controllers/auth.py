import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    confirm_login,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from sqlalchemy import func, or_

from database.models import Usuario
from extensions import db


auth_bp = Blueprint(
    "auth",
    __name__,
)


def endereco_local(endereco):
    if not endereco:
        return False

    endereco_base = urlparse(request.host_url)
    endereco_destino = urlparse(
        urljoin(request.host_url, endereco)
    )

    return (
        endereco_destino.scheme in ("http", "https")
        and endereco_base.netloc == endereco_destino.netloc
    )


def validar_nova_senha(senha):
    if len(senha) < 8:
        return "A senha deve ter pelo menos 8 caracteres."

    if not re.search(r"[A-Z]", senha):
        return "A senha deve possuir pelo menos uma letra maiúscula."

    if not re.search(r"[a-z]", senha):
        return "A senha deve possuir pelo menos uma letra minúscula."

    if not re.search(r"\d", senha):
        return "A senha deve possuir pelo menos um número."

    if not re.search(r"[^A-Za-z0-9]", senha):
        return "A senha deve possuir pelo menos um caractere especial."

    return None


@auth_bp.route(
    "/login",
    methods=["GET", "POST"],
)
def login():
    if current_user.is_authenticated:
        if current_user.trocar_senha:
            return redirect(
                url_for("auth.trocar_senha")
            )

        return redirect(
            url_for("dashboard")
        )

    if request.method == "POST":
        identificacao = (
            request.form
            .get("identificacao", "")
            .strip()
            .lower()
        )

        senha = request.form.get(
            "senha",
            "",
        )

        lembrar = (
            request.form.get("lembrar")
            == "on"
        )

        usuario = (
            Usuario.query
            .filter(
                or_(
                    func.lower(Usuario.usuario)
                    == identificacao,
                    func.lower(Usuario.email)
                    == identificacao,
                )
            )
            .first()
        )

        if usuario is None or not usuario.verificar_senha(senha):
            flash(
                "Usuário ou senha inválidos.",
                "danger",
            )

            return render_template(
                "login.html"
            )

        if not usuario.ativo:
            flash(
                "Este usuário está desativado. "
                "Entre em contato com o administrador.",
                "warning",
            )

            return render_template(
                "login.html"
            )

        login_user(
            usuario,
            remember=lembrar,
        )

        usuario.ultimo_acesso = datetime.utcnow()
        db.session.commit()

        if usuario.trocar_senha:
            return redirect(
                url_for("auth.trocar_senha")
            )

        destino = request.args.get("next")

        if destino and endereco_local(destino):
            return redirect(destino)

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "login.html"
    )


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()

    flash(
        "Sessão encerrada com sucesso.",
        "success",
    )

    return redirect(
        url_for("auth.login")
    )


@auth_bp.route(
    "/trocar-senha",
    methods=["GET", "POST"],
)
@login_required
def trocar_senha():
    if request.method == "POST":
        senha_atual = request.form.get(
            "senha_atual",
            "",
        )

        nova_senha = request.form.get(
            "nova_senha",
            "",
        )

        confirmar_senha = request.form.get(
            "confirmar_senha",
            "",
        )

        if not current_user.verificar_senha(senha_atual):
            flash(
                "A senha atual está incorreta.",
                "danger",
            )

            return render_template(
                "trocar_senha.html"
            )

        erro_senha = validar_nova_senha(
            nova_senha
        )

        if erro_senha:
            flash(
                erro_senha,
                "warning",
            )

            return render_template(
                "trocar_senha.html"
            )

        if nova_senha != confirmar_senha:
            flash(
                "A confirmação não corresponde à nova senha.",
                "warning",
            )

            return render_template(
                "trocar_senha.html"
            )

        if current_user.verificar_senha(nova_senha):
            flash(
                "A nova senha precisa ser diferente da senha atual.",
                "warning",
            )

            return render_template(
                "trocar_senha.html"
            )

        current_user.definir_senha(
            nova_senha
        )

        current_user.trocar_senha = False

        db.session.commit()

        confirm_login()

        flash(
            "Senha alterada com sucesso.",
            "success",
        )

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "trocar_senha.html"
    )