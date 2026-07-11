from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from database.models import (
    Abastecimento,
    Motorista,
    Obra,
    Veiculo,
)
from extensions import db


abastecimentos_bp = Blueprint(
    "abastecimentos",
    __name__,
)


EXTENSOES_PERMITIDAS = {
    "jpg",
    "jpeg",
    "png",
    "webp",
    "pdf",
}


COMBUSTIVEIS_PERMITIDOS = {
    "Gasolina",
    "Etanol",
    "Diesel",
    "Diesel S10",
    "Diesel S500",
    "GNV",
    "Elétrico",
    "Outro",
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


def converter_decimal(valor):
    if valor is None:
        return None

    texto = (
        str(valor)
        .strip()
        .replace("R$", "")
        .replace(" ", "")
    )

    if not texto:
        return None

    if "," in texto:
        texto = (
            texto
            .replace(".", "")
            .replace(",", ".")
        )

    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError):
        return None


def calcular_valor_total(litros, valor_litro):
    return (
        litros * valor_litro
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


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


def extensao_permitida(nome_arquivo):
    if "." not in nome_arquivo:
        return False

    extensao = (
        nome_arquivo
        .rsplit(".", 1)[1]
        .lower()
    )

    return extensao in EXTENSOES_PERMITIDAS


def salvar_comprovante(arquivo, empresa_id):
    if not arquivo or not arquivo.filename:
        return None

    nome_original = secure_filename(
        arquivo.filename
    )

    if not extensao_permitida(nome_original):
        raise ValueError(
            "O comprovante deve ser uma imagem JPG, PNG, WEBP ou um PDF."
        )

    extensao = (
        nome_original
        .rsplit(".", 1)[1]
        .lower()
    )

    nome_final = (
        f"{uuid4().hex}.{extensao}"
    )

    pasta_relativa = Path(
        "uploads",
        "abastecimentos",
        str(empresa_id),
    )

    pasta_absoluta = (
        Path(current_app.static_folder)
        / pasta_relativa
    )

    pasta_absoluta.mkdir(
        parents=True,
        exist_ok=True,
    )

    caminho_absoluto = (
        pasta_absoluta
        / nome_final
    )

    arquivo.save(caminho_absoluto)

    return (
        pasta_relativa
        / nome_final
    ).as_posix()


def remover_comprovante(caminho_relativo):
    if not caminho_relativo:
        return

    pasta_static = Path(
        current_app.static_folder
    ).resolve()

    caminho_absoluto = (
        pasta_static
        / caminho_relativo
    ).resolve()

    try:
        caminho_absoluto.relative_to(
            pasta_static
        )
    except ValueError:
        return

    if caminho_absoluto.exists():
        caminho_absoluto.unlink()


def obter_dados_formulario(empresa_id):
    data_registro = converter_data(
        request.form.get("data")
    )

    hora = converter_hora(
        request.form.get("hora")
    )

    posto = (
        request.form
        .get("posto", "")
        .strip()
    )

    combustivel = (
        request.form
        .get("combustivel", "")
        .strip()
    )

    litros = converter_decimal(
        request.form.get("litros")
    )

    valor_litro = converter_decimal(
        request.form.get("valor_litro")
    )

    km = converter_inteiro(
        request.form.get("km")
    )

    numero_nota = (
        request.form
        .get("numero_nota", "")
        .strip()
    )

    observacoes = (
        request.form
        .get("observacoes", "")
        .strip()
    )

    tanque_cheio = (
        request.form.get("tanque_cheio")
        == "on"
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

    return {
        "data": data_registro,
        "hora": hora,
        "posto": posto,
        "combustivel": combustivel,
        "litros": litros,
        "valor_litro": valor_litro,
        "km": km,
        "numero_nota": numero_nota,
        "observacoes": observacoes,
        "tanque_cheio": tanque_cheio,
        "veiculo": veiculo,
        "motorista": motorista,
        "obra": obra,
        "obra_id_informada": obra_id_informada,
    }


def validar_dados(dados):
    if dados["data"] is None:
        return "Informe uma data válida."

    if dados["veiculo"] is None:
        return "Selecione um veículo válido."

    if dados["motorista"] is None:
        return "Selecione um motorista válido."

    if (
        dados["obra_id_informada"]
        and dados["obra"] is None
    ):
        return "A obra selecionada não foi encontrada."

    if not dados["posto"]:
        return "Informe o posto ou fornecedor."

    if (
        dados["combustivel"]
        not in COMBUSTIVEIS_PERMITIDOS
    ):
        return "Selecione um combustível válido."

    if (
        dados["litros"] is None
        or dados["litros"] <= 0
    ):
        return (
            "A quantidade de litros deve ser maior que zero."
        )

    if (
        dados["valor_litro"] is None
        or dados["valor_litro"] <= 0
    ):
        return (
            "O valor por litro deve ser maior que zero."
        )

    if dados["km"] is None or dados["km"] < 0:
        return "Informe uma quilometragem válida."

    return None


def registro_duplicado(
    empresa_id,
    dados,
    abastecimento_id=None,
):
    consulta = Abastecimento.query.filter(
        Abastecimento.empresa_id == empresa_id,
        Abastecimento.veiculo_id
        == dados["veiculo"].id,
        Abastecimento.data == dados["data"],
        Abastecimento.km == dados["km"],
    )

    if dados["hora"] is None:
        consulta = consulta.filter(
            Abastecimento.hora.is_(None)
        )
    else:
        consulta = consulta.filter(
            Abastecimento.hora == dados["hora"]
        )

    if abastecimento_id is not None:
        consulta = consulta.filter(
            Abastecimento.id
            != abastecimento_id
        )

    return consulta.first()


@abastecimentos_bp.route(
    "/abastecimentos"
)
@login_required
def listar_abastecimentos():
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

    consulta = Abastecimento.query.filter_by(
        empresa_id=empresa.id
    )

    veiculo_filtro = request.args.get(
        "veiculo_id",
        type=int,
    )

    motorista_filtro = request.args.get(
        "motorista_id",
        type=int,
    )

    obra_filtro = request.args.get(
        "obra_id",
        type=int,
    )

    data_inicio_filtro = converter_data(
        request.args.get("data_inicio")
    )

    data_fim_filtro = converter_data(
        request.args.get("data_fim")
    )

    if veiculo_filtro:
        consulta = consulta.filter(
            Abastecimento.veiculo_id
            == veiculo_filtro
        )

    if motorista_filtro:
        consulta = consulta.filter(
            Abastecimento.motorista_id
            == motorista_filtro
        )

    if obra_filtro:
        consulta = consulta.filter(
            Abastecimento.obra_id
            == obra_filtro
        )

    if data_inicio_filtro:
        consulta = consulta.filter(
            Abastecimento.data
            >= data_inicio_filtro
        )

    if data_fim_filtro:
        consulta = consulta.filter(
            Abastecimento.data
            <= data_fim_filtro
        )

    abastecimentos = (
        consulta
        .order_by(
            Abastecimento.data.desc(),
            Abastecimento.hora.desc(),
            Abastecimento.id.desc(),
        )
        .all()
    )

    total_litros = sum(
        (
            abastecimento.litros
            for abastecimento in abastecimentos
        ),
        Decimal("0"),
    )

    total_valor = sum(
        (
            abastecimento.valor_total
            for abastecimento in abastecimentos
        ),
        Decimal("0"),
    )

    preco_medio = Decimal("0")

    if total_litros > 0:
        preco_medio = (
            total_valor / total_litros
        ).quantize(
            Decimal("0.001"),
            rounding=ROUND_HALF_UP,
        )

    agora = datetime.now()

    return render_template(
        "abastecimentos.html",
        abastecimentos=abastecimentos,
        veiculos=veiculos,
        motoristas=motoristas,
        obras=obras,
        total_registros=len(abastecimentos),
        total_litros=total_litros,
        total_valor=total_valor,
        preco_medio=preco_medio,
        hoje=date.today().isoformat(),
        hora_atual=agora.strftime("%H:%M"),
        veiculo_filtro=veiculo_filtro,
        motorista_filtro=motorista_filtro,
        obra_filtro=obra_filtro,
        data_inicio_filtro=request.args.get(
            "data_inicio",
            "",
        ),
        data_fim_filtro=request.args.get(
            "data_fim",
            "",
        ),
    )


@abastecimentos_bp.route(
    "/abastecimentos/novo",
    methods=["POST"],
)
@login_required
def novo_abastecimento():
    empresa = current_user.empresa

    dados = obter_dados_formulario(
        empresa.id
    )

    erro = validar_dados(dados)

    if erro:
        flash(
            erro,
            "warning",
        )

        return redirect(
            url_for(
                "abastecimentos.listar_abastecimentos"
            )
        )

    if registro_duplicado(
        empresa.id,
        dados,
    ):
        flash(
            "Já existe um abastecimento desse veículo "
            "com a mesma data, hora e quilometragem.",
            "warning",
        )

        return redirect(
            url_for(
                "abastecimentos.listar_abastecimentos"
            )
        )

    comprovante = None

    try:
        comprovante = salvar_comprovante(
            request.files.get("comprovante"),
            empresa.id,
        )
    except ValueError as erro_arquivo:
        flash(
            str(erro_arquivo),
            "warning",
        )

        return redirect(
            url_for(
                "abastecimentos.listar_abastecimentos"
            )
        )

    valor_total = calcular_valor_total(
        dados["litros"],
        dados["valor_litro"],
    )

    abastecimento = Abastecimento(
        empresa_id=empresa.id,
        usuario_id=current_user.id,
        veiculo_id=dados["veiculo"].id,
        motorista_id=dados["motorista"].id,
        obra_id=(
            dados["obra"].id
            if dados["obra"]
            else None
        ),
        data=dados["data"],
        hora=dados["hora"],
        posto=dados["posto"],
        combustivel=dados["combustivel"],
        litros=dados["litros"],
        valor_litro=dados["valor_litro"],
        valor_total=valor_total,
        km=dados["km"],
        tanque_cheio=dados["tanque_cheio"],
        numero_nota=(
            dados["numero_nota"]
            or None
        ),
        comprovante=comprovante,
        observacoes=(
            dados["observacoes"]
            or None
        ),
    )

    db.session.add(abastecimento)

    if dados["km"] > dados["veiculo"].km_atual:
        dados["veiculo"].km_atual = dados["km"]

    db.session.commit()

    flash(
        "Abastecimento registrado com sucesso.",
        "success",
    )

    return redirect(
        url_for(
            "abastecimentos.listar_abastecimentos"
        )
    )


@abastecimentos_bp.route(
    "/abastecimentos/<int:abastecimento_id>/editar",
    methods=["POST"],
)
@login_required
def editar_abastecimento(abastecimento_id):
    empresa = current_user.empresa

    abastecimento = (
        Abastecimento.query
        .filter_by(
            id=abastecimento_id,
            empresa_id=empresa.id,
        )
        .first()
    )

    if abastecimento is None:
        abort(404)

    dados = obter_dados_formulario(
        empresa.id
    )

    erro = validar_dados(dados)

    if erro:
        flash(
            erro,
            "warning",
        )

        return redirect(
            url_for(
                "abastecimentos.listar_abastecimentos"
            )
        )

    if registro_duplicado(
        empresa.id,
        dados,
        abastecimento_id=abastecimento.id,
    ):
        flash(
            "Já existe outro abastecimento com "
            "a mesma data, hora e quilometragem.",
            "warning",
        )

        return redirect(
            url_for(
                "abastecimentos.listar_abastecimentos"
            )
        )

    novo_arquivo = request.files.get(
        "comprovante"
    )

    novo_comprovante = None

    try:
        novo_comprovante = salvar_comprovante(
            novo_arquivo,
            empresa.id,
        )
    except ValueError as erro_arquivo:
        flash(
            str(erro_arquivo),
            "warning",
        )

        return redirect(
            url_for(
                "abastecimentos.listar_abastecimentos"
            )
        )

    comprovante_antigo = (
        abastecimento.comprovante
    )

    abastecimento.veiculo_id = (
        dados["veiculo"].id
    )

    abastecimento.motorista_id = (
        dados["motorista"].id
    )

    abastecimento.obra_id = (
        dados["obra"].id
        if dados["obra"]
        else None
    )

    abastecimento.data = dados["data"]
    abastecimento.hora = dados["hora"]
    abastecimento.posto = dados["posto"]

    abastecimento.combustivel = (
        dados["combustivel"]
    )

    abastecimento.litros = dados["litros"]

    abastecimento.valor_litro = (
        dados["valor_litro"]
    )

    abastecimento.valor_total = (
        calcular_valor_total(
            dados["litros"],
            dados["valor_litro"],
        )
    )

    abastecimento.km = dados["km"]

    abastecimento.tanque_cheio = (
        dados["tanque_cheio"]
    )

    abastecimento.numero_nota = (
        dados["numero_nota"]
        or None
    )

    abastecimento.observacoes = (
        dados["observacoes"]
        or None
    )

    if novo_comprovante:
        abastecimento.comprovante = (
            novo_comprovante
        )

    if dados["km"] > dados["veiculo"].km_atual:
        dados["veiculo"].km_atual = dados["km"]

    db.session.commit()

    if (
        novo_comprovante
        and comprovante_antigo
        and comprovante_antigo
        != novo_comprovante
    ):
        remover_comprovante(
            comprovante_antigo
        )

    flash(
        "Abastecimento atualizado com sucesso.",
        "success",
    )

    return redirect(
        url_for(
            "abastecimentos.listar_abastecimentos"
        )
    )