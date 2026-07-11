from datetime import date, datetime

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

from database.models import (
    DiarioBordo,
    Motorista,
    Obra,
    Veiculo,
)
from extensions import db


diario_bp = Blueprint(
    "diario",
    __name__,
)


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


def converter_hora(valor):
    if not valor:
        return None

    try:
        return datetime.strptime(
            valor,
            "%H:%M",
        ).time()
    except (TypeError, ValueError):
        return None


def converter_inteiro(valor):
    if valor is None or str(valor).strip() == "":
        return None

    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def buscar_veiculo(empresa_id, veiculo_id):
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


def buscar_motorista(empresa_id, motorista_id):
    try:
        motorista_id = int(motorista_id)
    except (TypeError, ValueError):
        return None

    return (
        Motorista.query
        .filter_by(
            id=motorista_id,
            empresa_id=empresa_id,
        )
        .first()
    )


def buscar_obra(empresa_id, obra_id):
    if not obra_id:
        return None

    try:
        obra_id = int(obra_id)
    except (TypeError, ValueError):
        return None

    return (
        Obra.query
        .filter_by(
            id=obra_id,
            empresa_id=empresa_id,
        )
        .first()
    )


def diario_aberto_do_veiculo(
    empresa_id,
    veiculo_id,
    diario_id=None,
):
    consulta = DiarioBordo.query.filter(
        DiarioBordo.empresa_id == empresa_id,
        DiarioBordo.veiculo_id == veiculo_id,
        DiarioBordo.status == "Em andamento",
    )

    if diario_id is not None:
        consulta = consulta.filter(
            DiarioBordo.id != diario_id
        )

    return consulta.first()


def diario_aberto_do_motorista(
    empresa_id,
    motorista_id,
    diario_id=None,
):
    consulta = DiarioBordo.query.filter(
        DiarioBordo.empresa_id == empresa_id,
        DiarioBordo.motorista_id == motorista_id,
        DiarioBordo.status == "Em andamento",
    )

    if diario_id is not None:
        consulta = consulta.filter(
            DiarioBordo.id != diario_id
        )

    return consulta.first()


def obter_dados_formulario(empresa_id):
    data_registro = converter_data(
        request.form.get("data")
    )

    hora_saida = converter_hora(
        request.form.get("hora_saida")
    )

    hora_retorno_informada = (
        request.form.get("hora_retorno", "")
        .strip()
    )

    hora_retorno = converter_hora(
        hora_retorno_informada
    )

    km_inicial = converter_inteiro(
        request.form.get("km_inicial")
    )

    km_final_informada = (
        request.form.get("km_final", "")
        .strip()
    )

    km_final = converter_inteiro(
        km_final_informada
    )

    origem = (
        request.form
        .get("origem", "")
        .strip()
    )

    destino = (
        request.form
        .get("destino", "")
        .strip()
    )

    finalidade = (
        request.form
        .get("finalidade", "")
        .strip()
    )

    ocorrencias = (
        request.form
        .get("ocorrencias", "")
        .strip()
    )

    veiculo = buscar_veiculo(
        empresa_id,
        request.form.get("veiculo_id"),
    )

    motorista = buscar_motorista(
        empresa_id,
        request.form.get("motorista_id"),
    )

    obra_id_informada = request.form.get(
        "obra_id",
        "",
    )

    obra = buscar_obra(
        empresa_id,
        obra_id_informada,
    )

    dados = {
        "data": data_registro,
        "hora_saida": hora_saida,
        "hora_retorno": hora_retorno,
        "hora_retorno_informada": hora_retorno_informada,
        "km_inicial": km_inicial,
        "km_final": km_final,
        "km_final_informada": km_final_informada,
        "origem": origem,
        "destino": destino,
        "finalidade": finalidade,
        "ocorrencias": ocorrencias,
        "veiculo": veiculo,
        "motorista": motorista,
        "obra": obra,
        "obra_id_informada": obra_id_informada,
    }

    return dados


def validar_dados(dados, empresa_id, diario_id=None):
    if dados["data"] is None:
        return "Informe uma data válida."

    if dados["hora_saida"] is None:
        return "Informe o horário de saída."

    if dados["veiculo"] is None:
        return "Selecione um veículo válido."

    if dados["motorista"] is None:
        return "Selecione um motorista válido."

    if (
        dados["obra_id_informada"]
        and dados["obra"] is None
    ):
        return "A obra selecionada não foi encontrada."

    if dados["km_inicial"] is None:
        return "Informe a quilometragem inicial."

    if dados["km_inicial"] < 0:
        return "A quilometragem inicial não pode ser negativa."

    if not dados["origem"]:
        return "Informe a origem do deslocamento."

    if not dados["destino"]:
        return "Informe o destino do deslocamento."

    possui_hora_retorno = bool(
        dados["hora_retorno_informada"]
    )

    possui_km_final = bool(
        dados["km_final_informada"]
    )

    if possui_hora_retorno != possui_km_final:
        return (
            "Para concluir o diário, informe a hora de retorno "
            "e a quilometragem final."
        )

    if possui_hora_retorno and dados["hora_retorno"] is None:
        return "Informe um horário de retorno válido."

    if possui_km_final and dados["km_final"] is None:
        return "Informe uma quilometragem final válida."

    if (
        dados["km_final"] is not None
        and dados["km_final"] < dados["km_inicial"]
    ):
        return (
            "A quilometragem final não pode ser menor "
            "que a quilometragem inicial."
        )

    diario_veiculo = diario_aberto_do_veiculo(
        empresa_id=empresa_id,
        veiculo_id=dados["veiculo"].id,
        diario_id=diario_id,
    )

    diario_motorista = diario_aberto_do_motorista(
        empresa_id=empresa_id,
        motorista_id=dados["motorista"].id,
        diario_id=diario_id,
    )

    registro_ficara_aberto = (
        dados["hora_retorno"] is None
        and dados["km_final"] is None
    )

    if registro_ficara_aberto and diario_veiculo:
        return (
            f"O veículo {dados['veiculo'].placa} já possui "
            "um diário de bordo em andamento."
        )

    if registro_ficara_aberto and diario_motorista:
        return (
            f"O motorista {dados['motorista'].nome} já possui "
            "um diário de bordo em andamento."
        )

    return None


@diario_bp.route("/diario")
@login_required
def listar_diarios():
    empresa = current_user.empresa

    veiculos = (
        Veiculo.query
        .filter_by(empresa_id=empresa.id)
        .order_by(Veiculo.placa.asc())
        .all()
    )

    motoristas = (
        Motorista.query
        .filter_by(empresa_id=empresa.id)
        .order_by(Motorista.nome.asc())
        .all()
    )

    obras = (
        Obra.query
        .filter_by(empresa_id=empresa.id)
        .order_by(Obra.nome.asc())
        .all()
    )

    consulta = DiarioBordo.query.filter_by(
        empresa_id=empresa.id
    )

    status_filtro = (
        request.args
        .get("status", "")
        .strip()
    )

    veiculo_filtro = request.args.get(
        "veiculo_id",
        type=int,
    )

    motorista_filtro = request.args.get(
        "motorista_id",
        type=int,
    )

    data_inicio_filtro = converter_data(
        request.args.get("data_inicio")
    )

    data_fim_filtro = converter_data(
        request.args.get("data_fim")
    )

    if status_filtro in (
        "Em andamento",
        "Concluído",
    ):
        consulta = consulta.filter(
            DiarioBordo.status == status_filtro
        )

    if veiculo_filtro:
        consulta = consulta.filter(
            DiarioBordo.veiculo_id == veiculo_filtro
        )

    if motorista_filtro:
        consulta = consulta.filter(
            DiarioBordo.motorista_id
            == motorista_filtro
        )

    if data_inicio_filtro:
        consulta = consulta.filter(
            DiarioBordo.data >= data_inicio_filtro
        )

    if data_fim_filtro:
        consulta = consulta.filter(
            DiarioBordo.data <= data_fim_filtro
        )

    diarios = (
        consulta
        .order_by(
            DiarioBordo.data.desc(),
            DiarioBordo.hora_saida.desc(),
            DiarioBordo.id.desc(),
        )
        .all()
    )

    todos_diarios = (
        DiarioBordo.query
        .filter_by(empresa_id=empresa.id)
        .all()
    )

    total_em_andamento = sum(
        1
        for diario in todos_diarios
        if diario.status == "Em andamento"
    )

    total_concluidos = sum(
        1
        for diario in todos_diarios
        if diario.status == "Concluído"
    )

    total_km = sum(
        diario.km_percorrida or 0
        for diario in todos_diarios
    )

    return render_template(
        "diario.html",
        diarios=diarios,
        veiculos=veiculos,
        motoristas=motoristas,
        obras=obras,
        hoje=date.today().isoformat(),
        total_diarios=len(todos_diarios),
        total_em_andamento=total_em_andamento,
        total_concluidos=total_concluidos,
        total_km=total_km,
        status_filtro=status_filtro,
        veiculo_filtro=veiculo_filtro,
        motorista_filtro=motorista_filtro,
        data_inicio_filtro=request.args.get(
            "data_inicio",
            "",
        ),
        data_fim_filtro=request.args.get(
            "data_fim",
            "",
        ),
    )


@diario_bp.route(
    "/diario/novo",
    methods=["POST"],
)
@login_required
def novo_diario():
    empresa = current_user.empresa

    dados = obter_dados_formulario(
        empresa.id
    )

    erro = validar_dados(
        dados=dados,
        empresa_id=empresa.id,
    )

    if erro:
        flash(
            erro,
            "warning",
        )

        return redirect(
            url_for("diario.listar_diarios")
        )

    status = (
        "Concluído"
        if dados["km_final"] is not None
        else "Em andamento"
    )

    diario = DiarioBordo(
        empresa_id=empresa.id,
        veiculo_id=dados["veiculo"].id,
        motorista_id=dados["motorista"].id,
        obra_id=(
            dados["obra"].id
            if dados["obra"]
            else None
        ),
        data=dados["data"],
        hora_saida=dados["hora_saida"],
        hora_retorno=dados["hora_retorno"],
        km_inicial=dados["km_inicial"],
        km_final=dados["km_final"],
        origem=dados["origem"],
        destino=dados["destino"],
        finalidade=dados["finalidade"] or None,
        ocorrencias=dados["ocorrencias"] or None,
        status=status,
    )

    db.session.add(diario)

    if (
        dados["km_final"] is not None
        and dados["km_final"]
        > dados["veiculo"].km_atual
    ):
        dados["veiculo"].km_atual = dados["km_final"]

    db.session.commit()

    flash(
        "Diário de bordo registrado com sucesso.",
        "success",
    )

    return redirect(
        url_for("diario.listar_diarios")
    )


@diario_bp.route(
    "/diario/<int:diario_id>/editar",
    methods=["POST"],
)
@login_required
def editar_diario(diario_id):
    empresa = current_user.empresa

    diario = (
        DiarioBordo.query
        .filter_by(
            id=diario_id,
            empresa_id=empresa.id,
        )
        .first()
    )

    if diario is None:
        abort(404)

    dados = obter_dados_formulario(
        empresa.id
    )

    erro = validar_dados(
        dados=dados,
        empresa_id=empresa.id,
        diario_id=diario.id,
    )

    if erro:
        flash(
            erro,
            "warning",
        )

        return redirect(
            url_for("diario.listar_diarios")
        )

    diario.veiculo_id = dados["veiculo"].id
    diario.motorista_id = dados["motorista"].id
    diario.obra_id = (
        dados["obra"].id
        if dados["obra"]
        else None
    )

    diario.data = dados["data"]
    diario.hora_saida = dados["hora_saida"]
    diario.hora_retorno = dados["hora_retorno"]
    diario.km_inicial = dados["km_inicial"]
    diario.km_final = dados["km_final"]
    diario.origem = dados["origem"]
    diario.destino = dados["destino"]
    diario.finalidade = dados["finalidade"] or None
    diario.ocorrencias = dados["ocorrencias"] or None

    diario.status = (
        "Concluído"
        if dados["km_final"] is not None
        else "Em andamento"
    )

    if (
        dados["km_final"] is not None
        and dados["km_final"]
        > dados["veiculo"].km_atual
    ):
        dados["veiculo"].km_atual = dados["km_final"]

    db.session.commit()

    flash(
        "Diário de bordo atualizado com sucesso.",
        "success",
    )

    return redirect(
        url_for("diario.listar_diarios")
    )