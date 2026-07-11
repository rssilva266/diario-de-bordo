import re
from datetime import datetime

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from database.models import Motorista, Veiculo
from extensions import db


motoristas_bp = Blueprint(
    "motoristas",
    __name__,
)


def somente_numeros(valor):
    return re.sub(
        r"\D",
        "",
        str(valor or ""),
    )


def formatar_cpf(valor):
    numeros = somente_numeros(valor)

    if len(numeros) != 11:
        return str(valor or "").strip()

    return (
        f"{numeros[:3]}."
        f"{numeros[3:6]}."
        f"{numeros[6:9]}-"
        f"{numeros[9:]}"
    )


def cpf_valido(valor):
    cpf = somente_numeros(valor)

    if len(cpf) != 11:
        return False

    if cpf == cpf[0] * 11:
        return False

    soma = sum(
        int(cpf[indice]) * (10 - indice)
        for indice in range(9)
    )

    primeiro_digito = (soma * 10) % 11

    if primeiro_digito == 10:
        primeiro_digito = 0

    if primeiro_digito != int(cpf[9]):
        return False

    soma = sum(
        int(cpf[indice]) * (11 - indice)
        for indice in range(10)
    )

    segundo_digito = (soma * 10) % 11

    if segundo_digito == 10:
        segundo_digito = 0

    return segundo_digito == int(cpf[10])


def converter_data(valor):
    try:
        return datetime.strptime(
            valor,
            "%Y-%m-%d",
        ).date()
    except (TypeError, ValueError):
        return None


def buscar_veiculo_da_empresa(empresa_id, veiculo_id):
    if not veiculo_id:
        return None

    try:
        veiculo_id = int(veiculo_id)
    except (TypeError, ValueError):
        return None

    return (
        Veiculo.query
        .filter_by(
            id=veiculo_id,
            empresa_id=empresa_id,
        )
        .first()
    )


def validar_dados_motorista(
    empresa_id,
    nome,
    cpf,
    cnh,
    categoria_cnh,
    validade_cnh,
    motorista_id=None,
):
    if not nome:
        return "Informe o nome do motorista."

    if not cpf_valido(cpf):
        return "Informe um CPF válido."

    if len(cnh) != 11:
        return "A CNH deve possuir 11 números."

    if not categoria_cnh:
        return "Selecione a categoria da CNH."

    if validade_cnh is None:
        return "Informe uma data de validade válida para a CNH."

    consulta_cpf = Motorista.query.filter(
        Motorista.empresa_id == empresa_id,
        Motorista.cpf == cpf,
    )

    if motorista_id is not None:
        consulta_cpf = consulta_cpf.filter(
            Motorista.id != motorista_id
        )

    if consulta_cpf.first():
        return "Já existe um motorista cadastrado com este CPF."

    consulta_cnh = Motorista.query.filter(
        Motorista.empresa_id == empresa_id,
        Motorista.cnh == cnh,
    )

    if motorista_id is not None:
        consulta_cnh = consulta_cnh.filter(
            Motorista.id != motorista_id
        )

    if consulta_cnh.first():
        return "Já existe um motorista cadastrado com esta CNH."

    return None


@motoristas_bp.route("/motoristas")
@login_required
def listar_motoristas():
    empresa = current_user.empresa

    motoristas = (
        Motorista.query
        .filter_by(empresa_id=empresa.id)
        .order_by(Motorista.nome.asc())
        .all()
    )

    veiculos = (
        Veiculo.query
        .filter_by(empresa_id=empresa.id)
        .order_by(Veiculo.placa.asc())
        .all()
    )

    total_ativos = sum(
        1
        for motorista in motoristas
        if motorista.status == "Ativo"
    )

    total_alertas = sum(
        1
        for motorista in motoristas
        if motorista.situacao_cnh in (
            "Vencida",
            "Vence em breve",
        )
    )

    return render_template(
        "motoristas.html",
        motoristas=motoristas,
        veiculos=veiculos,
        total_motoristas=len(motoristas),
        total_ativos=total_ativos,
        total_alertas=total_alertas,
    )


@motoristas_bp.route(
    "/motoristas/novo",
    methods=["POST"],
)
@login_required
def novo_motorista():
    empresa = current_user.empresa

    nome = (
        request.form
        .get("nome", "")
        .strip()
    )

    cpf = formatar_cpf(
        request.form.get("cpf", "")
    )

    cnh = somente_numeros(
        request.form.get("cnh")
    )

    categoria_cnh = (
        request.form
        .get("categoria_cnh", "")
        .strip()
        .upper()
    )

    validade_cnh = converter_data(
        request.form.get("validade_cnh")
    )

    telefone = (
        request.form
        .get("telefone", "")
        .strip()
    )

    status = (
        request.form
        .get("status", "Ativo")
        .strip()
    )

    observacoes = (
        request.form
        .get("observacoes", "")
        .strip()
    )

    veiculo_id_informado = request.form.get(
        "veiculo_id",
        "",
    )

    veiculo = buscar_veiculo_da_empresa(
        empresa.id,
        veiculo_id_informado,
    )

    if veiculo_id_informado and veiculo is None:
        flash(
            "O veículo selecionado não foi encontrado.",
            "warning",
        )

        return redirect(
            url_for("motoristas.listar_motoristas")
        )

    erro = validar_dados_motorista(
        empresa_id=empresa.id,
        nome=nome,
        cpf=cpf,
        cnh=cnh,
        categoria_cnh=categoria_cnh,
        validade_cnh=validade_cnh,
    )

    if erro:
        flash(
            erro,
            "warning",
        )

        return redirect(
            url_for("motoristas.listar_motoristas")
        )

    motorista = Motorista(
        empresa_id=empresa.id,
        veiculo_id=veiculo.id if veiculo else None,
        nome=nome,
        cpf=cpf,
        cnh=cnh,
        categoria_cnh=categoria_cnh,
        validade_cnh=validade_cnh,
        telefone=telefone or None,
        status=status,
        observacoes=observacoes or None,
    )

    db.session.add(motorista)
    db.session.commit()

    flash(
        "Motorista cadastrado com sucesso.",
        "success",
    )

    return redirect(
        url_for("motoristas.listar_motoristas")
    )


@motoristas_bp.route(
    "/motoristas/<int:motorista_id>/editar",
    methods=["POST"],
)
@login_required
def editar_motorista(motorista_id):
    empresa = current_user.empresa

    motorista = (
        Motorista.query
        .filter_by(
            id=motorista_id,
            empresa_id=empresa.id,
        )
        .first()
    )

    if motorista is None:
        abort(404)

    nome = (
        request.form
        .get("nome", "")
        .strip()
    )

    cpf = formatar_cpf(
        request.form.get("cpf", "")
    )

    cnh = somente_numeros(
        request.form.get("cnh")
    )

    categoria_cnh = (
        request.form
        .get("categoria_cnh", "")
        .strip()
        .upper()
    )

    validade_cnh = converter_data(
        request.form.get("validade_cnh")
    )

    telefone = (
        request.form
        .get("telefone", "")
        .strip()
    )

    status = (
        request.form
        .get("status", "Ativo")
        .strip()
    )

    observacoes = (
        request.form
        .get("observacoes", "")
        .strip()
    )

    veiculo_id_informado = request.form.get(
        "veiculo_id",
        "",
    )

    veiculo = buscar_veiculo_da_empresa(
        empresa.id,
        veiculo_id_informado,
    )

    if veiculo_id_informado and veiculo is None:
        flash(
            "O veículo selecionado não foi encontrado.",
            "warning",
        )

        return redirect(
            url_for("motoristas.listar_motoristas")
        )

    erro = validar_dados_motorista(
        empresa_id=empresa.id,
        nome=nome,
        cpf=cpf,
        cnh=cnh,
        categoria_cnh=categoria_cnh,
        validade_cnh=validade_cnh,
        motorista_id=motorista.id,
    )

    if erro:
        flash(
            erro,
            "warning",
        )

        return redirect(
            url_for("motoristas.listar_motoristas")
        )

    motorista.nome = nome
    motorista.cpf = cpf
    motorista.cnh = cnh
    motorista.categoria_cnh = categoria_cnh
    motorista.validade_cnh = validade_cnh
    motorista.telefone = telefone or None
    motorista.status = status
    motorista.observacoes = observacoes or None
    motorista.veiculo_id = (
        veiculo.id
        if veiculo
        else None
    )

    db.session.commit()

    flash(
        "Motorista atualizado com sucesso.",
        "success",
    )

    return redirect(
        url_for("motoristas.listar_motoristas")
    )