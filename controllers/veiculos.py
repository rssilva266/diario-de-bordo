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
        str(valor).upper(),
    )[:7]

    if len(placa_limpa) <= 3:
        return placa_limpa

    return f"{placa_limpa[:3]}-{placa_limpa[3:]}"


def placa_valida(placa):
    return bool(
        PADRAO_PLACA_ANTIGA.fullmatch(placa)
        or PADRAO_PLACA_MERCOSUL.fullmatch(placa)
    )


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

    limite_veiculos = empresa.plano.limite_veiculos

    if total_veiculos >= limite_veiculos:
        flash(
            f"O plano {empresa.plano.nome} permite até "
            f"{limite_veiculos} veículos. "
            "Faça upgrade para continuar.",
            "warning",
        )

        return redirect(
            url_for("veiculos.listar_veiculos")
        )

    placa = normalizar_placa(
        request.form.get("placa", "")
    )

    modelo = (
        request.form
        .get("modelo", "")
        .strip()
    )

    ano = inteiro_ou_none(
        request.form.get("ano")
    )

    combustivel = (
        request.form
        .get("combustivel", "")
        .strip()
    )

    km_atual = (
        inteiro_ou_none(
            request.form.get("km_atual")
        )
        or 0
    )

    if not placa or not modelo:
        flash(
            "Preencha a placa e o modelo do veículo.",
            "warning",
        )

        return redirect(
            url_for("veiculos.listar_veiculos")
        )

    if not placa_valida(placa):
        flash(
            "Informe uma placa válida nos formatos "
            "ABC-1234 ou ABC-1D23.",
            "warning",
        )

        return redirect(
            url_for("veiculos.listar_veiculos")
        )

    veiculo_existente = (
        Veiculo.query
        .filter_by(
            empresa_id=empresa.id,
            placa=placa,
        )
        .first()
    )

    if veiculo_existente:
        flash(
            f"Já existe um veículo com a placa {placa}.",
            "warning",
        )

        return redirect(
            url_for("veiculos.listar_veiculos")
        )

    veiculo = Veiculo(
        empresa_id=empresa.id,
        placa=placa,
        modelo=modelo,
        ano=ano,
        combustivel=combustivel,
        km_atual=km_atual,
        status="Ativo",
    )

    db.session.add(veiculo)
    db.session.commit()

    flash(
        "Veículo cadastrado com sucesso.",
        "success",
    )

    return redirect(
        url_for("veiculos.listar_veiculos")
    )