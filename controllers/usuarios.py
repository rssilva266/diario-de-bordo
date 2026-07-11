from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from database.models import Usuario
from extensions import db


usuarios_bp = Blueprint("usuarios", __name__)


def administrador():
    return (current_user.perfil or "").strip().lower() == "administrador"


@usuarios_bp.route("/cadastros/usuarios")
@login_required
def listar_usuarios():
    if not administrador():
        flash("Acesso permitido somente para administradores.", "warning")
        return redirect(url_for("dashboard"))

    usuarios = (
        Usuario.query
        .filter_by(empresa_id=current_user.empresa_id)
        .order_by(Usuario.nome.asc())
        .all()
    )
    return render_template("usuarios.html", usuarios=usuarios)


@usuarios_bp.route("/cadastros/usuarios/novo", methods=["POST"])
@login_required
def novo_usuario():
    if not administrador():
        flash("Acesso permitido somente para administradores.", "warning")
        return redirect(url_for("dashboard"))

    nome = request.form.get("nome", "").strip()
    usuario_login = request.form.get("usuario", "").strip().lower()
    email = request.form.get("email", "").strip().lower() or None
    perfil = request.form.get("perfil", "Operador").strip()
    senha = request.form.get("senha", "")

    if not nome or not usuario_login or len(senha) < 6:
        flash("Informe nome, usuário e senha com pelo menos 6 caracteres.", "warning")
        return redirect(url_for("usuarios.listar_usuarios"))

    duplicado = Usuario.query.filter(
        or_(Usuario.usuario == usuario_login, Usuario.email == email if email else False)
    ).first()
    if duplicado:
        flash("Usuário ou e-mail já cadastrado.", "warning")
        return redirect(url_for("usuarios.listar_usuarios"))

    usuario = Usuario(
        nome=nome,
        usuario=usuario_login,
        email=email,
        perfil=perfil,
        ativo=True,
        trocar_senha=True,
        empresa_id=current_user.empresa_id,
    )
    usuario.definir_senha(senha)

    try:
        db.session.add(usuario)
        db.session.commit()
        flash("Usuário cadastrado com sucesso.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Não foi possível cadastrar o usuário.", "danger")

    return redirect(url_for("usuarios.listar_usuarios"))


@usuarios_bp.route("/cadastros/usuarios/<int:usuario_id>/status", methods=["POST"])
@login_required
def alterar_status(usuario_id):
    if not administrador():
        flash("Acesso permitido somente para administradores.", "warning")
        return redirect(url_for("dashboard"))

    usuario = Usuario.query.filter_by(
        id=usuario_id,
        empresa_id=current_user.empresa_id,
    ).first_or_404()

    if usuario.id == current_user.id:
        flash("Você não pode desativar o próprio usuário.", "warning")
    else:
        usuario.ativo = not usuario.ativo
        db.session.commit()
        flash("Status do usuário atualizado.", "success")

    return redirect(url_for("usuarios.listar_usuarios"))
