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

from database.models import Obra, Veiculo
from extensions import db


obras_bp = Blueprint(
    "obras",
    __name__,
)


STATUS_PERMITIDOS = {
    "Planejada",
    "Ativa",
    "Pausada",
    "Concluída",
    "Cancelada",
}


def converter_data(valor):
    if not valor:
        return None

    try:
        return datetime.strptime(
            valor,
            "%Y-%m-%d",
        ).date()
    except (TypeError, ValueError):
        return None


def normalizar_codigo(valor):
    return (
        str(valor or "")
        .strip()
        .upper()
    )


def obter_ids_veiculos_formulario():
    ids_recebidos = request.form.getlist(
        "veiculos_ids"
    )

    ids_validos = set()

    for valor in ids_recebidos:
        try:
            ids_validos.add(int(valor))
        except (TypeError, ValueError):
            continue

    return ids_validos


def buscar_veiculos_da_empresa(
    empresa_id,
    ids_veiculos,
):
    if not ids_veiculos:
        return []

    veiculos = (
        Veiculo.query
        .filter(
            Veiculo.empresa_id == empresa_id,
            Veiculo.id.in_(ids_veiculos),
        )
        .all()
    )

    if len(veiculos) != len(ids_veiculos):
        return None

    return veiculos


def validar_dados_obra(
    empresa_id,
    codigo,
    nome,
    data_inicio,
    data_fim_prevista,
    status,
    obra_id=None,
):
    if not codigo:
        return "Informe o código da obra."

    if not nome:
        return "Informe o nome da obra."

    if status not in STATUS_PERMITIDOS:
        return "Selecione um status válido."

    if (
        data_inicio
        and data_fim_prevista
        and data_fim_prevista < data_inicio
    ):
        return (
            "A data prevista de término não pode ser "
            "anterior à data de início."
        )

    consulta_codigo = Obra.query.filter(
        Obra.empresa_id == empresa_id,
        Obra.codigo == codigo,
    )

    if obra_id is not None:
        consulta_codigo = consulta_codigo.filter(
            Obra.id != obra_id
        )

    if consulta_codigo.first():
        return (
            "Já existe uma obra cadastrada com este código."
        )

    return None


@obras_bp.route("/obras")
@login_required
def listar_obras():
    empresa = current_user.empresa

    obras = (
        Obra.query
        .filter_by(empresa_id=empresa.id)
        .order_by(
            Obra.status.asc(),
            Obra.nome.asc(),
        )
        .all()
    )

    veiculos = (
        Veiculo.query
        .filter_by(empresa_id=empresa.id)
        .order_by(Veiculo.placa.asc())
        .all()
    )

    total_ativas = sum(
        1
        for obra in obras
        if obra.status == "Ativa"
    )

    total_concluidas = sum(
        1
        for obra in obras
        if obra.status == "Concluída"
    )

    veiculos_vinculados = sum(
        1
        for veiculo in veiculos
        if veiculo.obra_id is not None
    )

    return render_template(
        "obras.html",
        obras=obras,
        veiculos=veiculos,
        total_obras=len(obras),
        total_ativas=total_ativas,
        total_concluidas=total_concluidas,
        veiculos_vinculados=veiculos_vinculados,
    )


@obras_bp.route(
    "/obras/nova",
    methods=["POST"],
)
@login_required
def nova_obra():
    empresa = current_user.empresa

    codigo = normalizar_codigo(
        request.form.get("codigo")
    )

    nome = (
        request.form
        .get("nome", "")
        .strip()
    )

    cliente = (
        request.form
        .get("cliente", "")
        .strip()
    )

    localizacao = (
        request.form
        .get("localizacao", "")
        .strip()
    )

    responsavel = (
        request.form
        .get("responsavel", "")
        .strip()
    )

    data_inicio = converter_data(
        request.form.get("data_inicio")
    )

    data_fim_prevista = converter_data(
        request.form.get("data_fim_prevista")
    )

    status = (
        request.form
        .get("status", "Planejada")
        .strip()
    )

    observacoes = (
        request.form
        .get("observacoes", "")
        .strip()
    )

    ids_veiculos = obter_ids_veiculos_formulario()

    veiculos_selecionados = buscar_veiculos_da_empresa(
        empresa.id,
        ids_veiculos,
    )

    if veiculos_selecionados is None:
        flash(
            "Um ou mais veículos selecionados são inválidos.",
            "warning",
        )

        return redirect(
            url_for("obras.listar_obras")
        )

    erro = validar_dados_obra(
        empresa_id=empresa.id,
        codigo=codigo,
        nome=nome,
        data_inicio=data_inicio,
        data_fim_prevista=data_fim_prevista,
        status=status,
    )

    if erro:
        flash(
            erro,
            "warning",
        )

        return redirect(
            url_for("obras.listar_obras")
        )

    obra = Obra(
        empresa_id=empresa.id,
        codigo=codigo,
        nome=nome,
        cliente=cliente or None,
        localizacao=localizacao or None,
        responsavel=responsavel or None,
        data_inicio=data_inicio,
        data_fim_prevista=data_fim_prevista,
        status=status,
        observacoes=observacoes or None,
    )

    db.session.add(obra)
    db.session.flush()

    for veiculo in veiculos_selecionados:
        veiculo.obra_id = obra.id

    db.session.commit()

    flash(
        "Obra cadastrada com sucesso.",
        "success",
    )

    return redirect(
        url_for("obras.listar_obras")
    )


@obras_bp.route(
    "/obras/<int:obra_id>/editar",
    methods=["POST"],
)
@login_required
def editar_obra(obra_id):
    empresa = current_user.empresa

    obra = (
        Obra.query
        .filter_by(
            id=obra_id,
            empresa_id=empresa.id,
        )
        .first()
    )

    if obra is None:
        abort(404)

    codigo = normalizar_codigo(
        request.form.get("codigo")
    )

    nome = (
        request.form
        .get("nome", "")
        .strip()
    )

    cliente = (
        request.form
        .get("cliente", "")
        .strip()
    )

    localizacao = (
        request.form
        .get("localizacao", "")
        .strip()
    )

    responsavel = (
        request.form
        .get("responsavel", "")
        .strip()
    )

    data_inicio = converter_data(
        request.form.get("data_inicio")
    )

    data_fim_prevista = converter_data(
        request.form.get("data_fim_prevista")
    )

    status = (
        request.form
        .get("status", "Planejada")
        .strip()
    )

    observacoes = (
        request.form
        .get("observacoes", "")
        .strip()
    )

    ids_veiculos = obter_ids_veiculos_formulario()

    veiculos_selecionados = buscar_veiculos_da_empresa(
        empresa.id,
        ids_veiculos,
    )

    if veiculos_selecionados is None:
        flash(
            "Um ou mais veículos selecionados são inválidos.",
            "warning",
        )

        return redirect(
            url_for("obras.listar_obras")
        )

    erro = validar_dados_obra(
        empresa_id=empresa.id,
        codigo=codigo,
        nome=nome,
        data_inicio=data_inicio,
        data_fim_prevista=data_fim_prevista,
        status=status,
        obra_id=obra.id,
    )

    if erro:
        flash(
            erro,
            "warning",
        )

        return redirect(
            url_for("obras.listar_obras")
        )

    obra.codigo = codigo
    obra.nome = nome
    obra.cliente = cliente or None
    obra.localizacao = localizacao or None
    obra.responsavel = responsavel or None
    obra.data_inicio = data_inicio
    obra.data_fim_prevista = data_fim_prevista
    obra.status = status
    obra.observacoes = observacoes or None

    veiculos_atualmente_vinculados = (
        Veiculo.query
        .filter_by(
            empresa_id=empresa.id,
            obra_id=obra.id,
        )
        .all()
    )

    for veiculo in veiculos_atualmente_vinculados:
        if veiculo.id not in ids_veiculos:
            veiculo.obra_id = None

    for veiculo in veiculos_selecionados:
        veiculo.obra_id = obra.id

    db.session.commit()

    flash(
        "Obra atualizada com sucesso.",
        "success",
    )

    return redirect(
        url_for("obras.listar_obras")
    )