import re

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from database.models import Veiculo
from extensions import db


veiculos_bp = Blueprint(
    "veiculos",
    __name__,
)


PADRAO_PLACA_ANTIGA = re.compile(
    r"^[A-Z]{3}-\d{4}$"
)

PADRAO_PLACA_MERCOSUL = re.compile(
    r"^[A-Z]{3}-\d[A-Z]\d{2}$"
)

STATUS_PERMITIDOS = {
    "Ativo",
    "Em manutenção",
    "Inativo",
}


def inteiro_ou_none(valor):
    if valor is None or str(valor).strip() == "":
        return None

    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def normalizar_placa(valor):
    placa_limpa = re.sub(
        r"[^A-Z0-9]",
        "",
        str(valor or "").upper(),
    )[:7]

    if len(placa_limpa) <= 3:
        return placa_limpa

    return (
        f"{placa_limpa[:3]}-"
        f"{placa_limpa[3:]}"
    )


def placa_valida(placa):
    return bool(
        PADRAO_PLACA_ANTIGA.fullmatch(placa)
        or PADRAO_PLACA_MERCOSUL.fullmatch(placa)
    )


def obter_dados_formulario():
    placa = normalizar_placa(
        request.form.get("placa", "")
    )

    modelo = (
        request.form
        .get("modelo", "")
        .strip()
    )

    ano_texto = (
        request.form
        .get("ano", "")
        .strip()
    )

    km_texto = (
        request.form
        .get("km_atual", "")
        .strip()
    )

    ano = inteiro_ou_none(ano_texto)
    km_atual = inteiro_ou_none(km_texto)

    combustivel = (
        request.form
        .get("combustivel", "")
        .strip()
    )

    status = (
        request.form
        .get("status", "Ativo")
        .strip()
    )

    return {
        "placa": placa,
        "modelo": modelo,
        "ano_texto": ano_texto,
        "ano": ano,
        "km_texto": km_texto,
        "km_atual": km_atual,
        "combustivel": combustivel,
        "status": status,
    }


def validar_dados_veiculo(
    empresa_id,
    dados,
    veiculo_id=None,
):
    placa = dados["placa"]
    modelo = dados["modelo"]
    ano_texto = dados["ano_texto"]
    ano = dados["ano"]
    km_texto = dados["km_texto"]
    km_atual = dados["km_atual"]
    status = dados["status"]

    if not placa:
        return "Informe a placa do veículo."

    if not placa_valida(placa):
        return (
            "Informe uma placa válida nos formatos "
            "ABC-1234 ou ABC-1D23."
        )

    if not modelo:
        return "Informe o modelo do veículo."

    if ano_texto:
        if ano is None:
            return "Informe um ano válido."

        if ano < 1900 or ano > 2100:
            return (
                "O ano do veículo deve estar "
                "entre 1900 e 2100."
            )

    if km_texto:
        if km_atual is None:
            return "Informe uma quilometragem válida."

        if km_atual < 0:
            return (
                "A quilometragem não pode "
                "ser negativa."
            )

    if status not in STATUS_PERMITIDOS:
        return "Selecione um status válido."

    consulta = Veiculo.query.filter(
        Veiculo.empresa_id == empresa_id,
        Veiculo.placa == placa,
    )

    if veiculo_id is not None:
        consulta = consulta.filter(
            Veiculo.id != veiculo_id
        )

    if consulta.first():
        return (
            f"Já existe um veículo com a placa "
            f"{placa}."
        )

    return None


@veiculos_bp.route("/veiculos")
@login_required
def listar_veiculos():
    empresa = current_user.empresa

    veiculos = (
        Veiculo.query
        .filter_by(empresa_id=empresa.id)
        .order_by(Veiculo.placa.asc())
        .all()
    )

    return render_template(
        "veiculos.html",
        veiculos=veiculos,
        empresa=empresa,
        total_veiculos=len(veiculos),
    )


@veiculos_bp.route(
    "/veiculos/novo",
    methods=["POST"],
)
@login_required
def novo_veiculo():
    empresa = current_user.empresa

    total_veiculos = (
        Veiculo.query
        .filter_by(empresa_id=empresa.id)
        .count()
    )

    limite_veiculos = (
        empresa.plano.limite_veiculos
    )

    if total_veiculos >= limite_veiculos:
        flash(
            f"O plano {empresa.plano.nome} permite até "
            f"{limite_veiculos} veículos. "
            "Faça upgrade para continuar.",
            "warning",
        )

        return redirect(
            url_for(
                "veiculos.listar_veiculos"
            )
        )

    dados = obter_dados_formulario()

    dados["status"] = "Ativo"

    erro = validar_dados_veiculo(
        empresa_id=empresa.id,
        dados=dados,
    )

    if erro:
        flash(
            erro,
            "warning",
        )

        return redirect(
            url_for(
                "veiculos.listar_veiculos"
            )
        )

    veiculo = Veiculo(
        empresa_id=empresa.id,
        placa=dados["placa"],
        modelo=dados["modelo"],
        ano=dados["ano"],
        combustivel=(
            dados["combustivel"]
            or None
        ),
        km_atual=(
            dados["km_atual"]
            if dados["km_atual"] is not None
            else 0
        ),
        status="Ativo",
    )

    try:
        db.session.add(veiculo)
        db.session.commit()

    except IntegrityError:
        db.session.rollback()

        flash(
            "Não foi possível cadastrar o veículo. "
            "Verifique se a placa já está cadastrada.",
            "danger",
        )

        return redirect(
            url_for(
                "veiculos.listar_veiculos"
            )
        )

    flash(
        "Veículo cadastrado com sucesso.",
        "success",
    )

    return redirect(
        url_for(
            "veiculos.listar_veiculos"
        )
    )


@veiculos_bp.route(
    "/veiculos/<int:veiculo_id>/editar",
    methods=["POST"],
)
@login_required
def editar_veiculo(veiculo_id):
    empresa = current_user.empresa

    veiculo = (
        Veiculo.query
        .filter_by(
            id=veiculo_id,
            empresa_id=empresa.id,
        )
        .first_or_404()
    )

    dados = obter_dados_formulario()

    erro = validar_dados_veiculo(
        empresa_id=empresa.id,
        dados=dados,
        veiculo_id=veiculo.id,
    )

    if erro:
        flash(
            erro,
            "warning",
        )

        return redirect(
            url_for(
                "veiculos.listar_veiculos"
            )
        )

    veiculo.placa = dados["placa"]
    veiculo.modelo = dados["modelo"]
    veiculo.ano = dados["ano"]

    veiculo.combustivel = (
        dados["combustivel"]
        or None
    )

    veiculo.km_atual = (
        dados["km_atual"]
        if dados["km_atual"] is not None
        else 0
    )

    veiculo.status = dados["status"]

    try:
        db.session.commit()

    except IntegrityError:
        db.session.rollback()

        flash(
            "Não foi possível atualizar o veículo. "
            "Verifique se a placa já está cadastrada.",
            "danger",
        )

        return redirect(
            url_for(
                "veiculos.listar_veiculos"
            )
        )

    flash(
        "Veículo atualizado com sucesso.",
        "success",
    )

    return redirect(
        url_for(
            "veiculos.listar_veiculos"
        )
    )