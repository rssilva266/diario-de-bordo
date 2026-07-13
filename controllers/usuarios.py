from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from database.models import Usuario
from extensions import db


usuarios_bp = Blueprint(
    "usuarios",
    __name__,
)


PERFIS_PERMITIDOS = {
    "Administrador",
    "Gestor",
    "Frota",
    "RH",
    "Motorista",
    "Operador",
}


def administrador():
    return (
        (current_user.perfil or "")
        .strip()
        .lower()
        == "administrador"
    )


def normalizar_usuario(valor):
    return (
        str(valor or "")
        .strip()
        .lower()
    )


def normalizar_email(valor):
    email = (
        str(valor or "")
        .strip()
        .lower()
    )

    return email or None


def perfil_valido(perfil):
    return perfil in PERFIS_PERMITIDOS


def buscar_duplicidade(
    usuario_login,
    email,
    ignorar_usuario_id=None,
):
    consulta = Usuario.query.filter(
        or_(
            func.lower(Usuario.usuario)
            == usuario_login.lower(),
            (
                func.lower(Usuario.email)
                == email.lower()
                if email
                else False
            ),
        )
    )

    if ignorar_usuario_id is not None:
        consulta = consulta.filter(
            Usuario.id != ignorar_usuario_id
        )

    return consulta.first()


def quantidade_administradores_ativos(
    empresa_id,
):
    return (
        Usuario.query
        .filter(
            Usuario.empresa_id == empresa_id,
            Usuario.ativo.is_(True),
            func.lower(Usuario.perfil)
            == "administrador",
        )
        .count()
    )


@usuarios_bp.route(
    "/cadastros/usuarios"
)
@login_required
def listar_usuarios():
    if not administrador():
        flash(
            "Acesso permitido somente para administradores.",
            "warning",
        )

        return redirect(
            url_for("dashboard")
        )

    usuarios = (
        Usuario.query
        .filter_by(
            empresa_id=current_user.empresa_id
        )
        .order_by(
            Usuario.nome.asc()
        )
        .all()
    )

    return render_template(
        "usuarios.html",
        usuarios=usuarios,
        perfis=sorted(PERFIS_PERMITIDOS),
    )


@usuarios_bp.route(
    "/cadastros/usuarios/novo",
    methods=["POST"],
)
@login_required
def novo_usuario():
    if not administrador():
        flash(
            "Acesso permitido somente para administradores.",
            "warning",
        )

        return redirect(
            url_for("dashboard")
        )

    nome = (
        request.form
        .get("nome", "")
        .strip()
    )

    usuario_login = normalizar_usuario(
        request.form.get("usuario")
    )

    email = normalizar_email(
        request.form.get("email")
    )

    perfil = (
        request.form
        .get("perfil", "Operador")
        .strip()
    )

    senha = request.form.get(
        "senha",
        "",
    )

    if not nome:
        flash(
            "Informe o nome do usuário.",
            "warning",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    if not usuario_login:
        flash(
            "Informe o usuário de acesso.",
            "warning",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    if len(usuario_login) < 3:
        flash(
            "O usuário de acesso deve possuir "
            "pelo menos 3 caracteres.",
            "warning",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    if not perfil_valido(perfil):
        flash(
            "Selecione um perfil válido.",
            "warning",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    if len(senha) < 6:
        flash(
            "A senha temporária deve possuir "
            "pelo menos 6 caracteres.",
            "warning",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    duplicado = buscar_duplicidade(
        usuario_login=usuario_login,
        email=email,
    )

    if duplicado:
        flash(
            "Usuário ou e-mail já cadastrado.",
            "warning",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

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

    except IntegrityError:
        db.session.rollback()

        flash(
            "Não foi possível cadastrar o usuário. "
            "Verifique o login e o e-mail informados.",
            "danger",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    flash(
        "Usuário cadastrado com sucesso.",
        "success",
    )

    return redirect(
        url_for(
            "usuarios.listar_usuarios"
        )
    )


@usuarios_bp.route(
    "/cadastros/usuarios/<int:usuario_id>/editar",
    methods=["POST"],
)
@login_required
def editar_usuario(usuario_id):
    if not administrador():
        flash(
            "Acesso permitido somente para administradores.",
            "warning",
        )

        return redirect(
            url_for("dashboard")
        )

    usuario = (
        Usuario.query
        .filter_by(
            id=usuario_id,
            empresa_id=current_user.empresa_id,
        )
        .first_or_404()
    )

    nome = (
        request.form
        .get("nome", "")
        .strip()
    )

    usuario_login = normalizar_usuario(
        request.form.get("usuario")
    )

    email = normalizar_email(
        request.form.get("email")
    )

    perfil = (
        request.form
        .get("perfil", "Operador")
        .strip()
    )

    nova_senha = request.form.get(
        "nova_senha",
        "",
    )

    exigir_troca_senha = (
        request.form.get(
            "exigir_troca_senha"
        )
        == "1"
    )

    if not nome:
        flash(
            "Informe o nome do usuário.",
            "warning",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    if not usuario_login:
        flash(
            "Informe o usuário de acesso.",
            "warning",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    if len(usuario_login) < 3:
        flash(
            "O usuário de acesso deve possuir "
            "pelo menos 3 caracteres.",
            "warning",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    if not perfil_valido(perfil):
        flash(
            "Selecione um perfil válido.",
            "warning",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    if nova_senha and len(nova_senha) < 6:
        flash(
            "A nova senha deve possuir "
            "pelo menos 6 caracteres.",
            "warning",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    usuario_era_administrador = (
        (usuario.perfil or "")
        .strip()
        .lower()
        == "administrador"
    )

    novo_perfil_administrador = (
        perfil.lower()
        == "administrador"
    )

    if (
        usuario.id == current_user.id
        and not novo_perfil_administrador
    ):
        flash(
            "Você não pode remover o perfil "
            "administrativo da própria conta.",
            "warning",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    if (
        usuario_era_administrador
        and usuario.ativo
        and not novo_perfil_administrador
        and quantidade_administradores_ativos(
            current_user.empresa_id
        ) <= 1
    ):
        flash(
            "A empresa precisa manter pelo menos "
            "um administrador ativo.",
            "warning",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    duplicado = buscar_duplicidade(
        usuario_login=usuario_login,
        email=email,
        ignorar_usuario_id=usuario.id,
    )

    if duplicado:
        flash(
            "Usuário ou e-mail já utilizado "
            "por outra conta.",
            "warning",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    usuario.nome = nome
    usuario.usuario = usuario_login
    usuario.email = email
    usuario.perfil = perfil

    if nova_senha:
        usuario.definir_senha(
            nova_senha
        )

        usuario.trocar_senha = (
            exigir_troca_senha
        )

    try:
        db.session.commit()

    except IntegrityError:
        db.session.rollback()

        flash(
            "Não foi possível atualizar o usuário. "
            "Verifique o login e o e-mail informados.",
            "danger",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    flash(
        "Usuário atualizado com sucesso.",
        "success",
    )

    return redirect(
        url_for(
            "usuarios.listar_usuarios"
        )
    )


@usuarios_bp.route(
    "/cadastros/usuarios/<int:usuario_id>/status",
    methods=["POST"],
)
@login_required
def alterar_status(usuario_id):
    if not administrador():
        flash(
            "Acesso permitido somente para administradores.",
            "warning",
        )

        return redirect(
            url_for("dashboard")
        )

    usuario = (
        Usuario.query
        .filter_by(
            id=usuario_id,
            empresa_id=current_user.empresa_id,
        )
        .first_or_404()
    )

    if usuario.id == current_user.id:
        flash(
            "Você não pode desativar o próprio usuário.",
            "warning",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    usuario_administrador = (
        (usuario.perfil or "")
        .strip()
        .lower()
        == "administrador"
    )

    if (
        usuario.ativo
        and usuario_administrador
        and quantidade_administradores_ativos(
            current_user.empresa_id
        ) <= 1
    ):
        flash(
            "A empresa precisa manter pelo menos "
            "um administrador ativo.",
            "warning",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    usuario.ativo = not usuario.ativo

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()

        flash(
            "Não foi possível alterar o status "
            "do usuário.",
            "danger",
        )

        return redirect(
            url_for(
                "usuarios.listar_usuarios"
            )
        )

    estado = (
        "ativado"
        if usuario.ativo
        else "desativado"
    )

    flash(
        f"Usuário {estado} com sucesso.",
        "success",
    )

    return redirect(
        url_for(
            "usuarios.listar_usuarios"
        )
    )