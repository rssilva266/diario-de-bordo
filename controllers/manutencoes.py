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

from database.models import Manutencao, Obra, Veiculo
from extensions import db


manutencoes_bp = Blueprint(
    "manutencoes",
    __name__,
)


TIPOS_PERMITIDOS = {
    "Preventiva",
    "Corretiva",
    "Revisão",
    "Troca de óleo",
    "Pneus",
    "Elétrica",
    "Mecânica",
    "Funilaria",
    "Outro",
}


STATUS_PERMITIDOS = {
    "Agendada",
    "Em andamento",
    "Aguardando peça",
    "Concluída",
    "Cancelada",
}


STATUS_VEICULO_EM_MANUTENCAO = {
    "Em andamento",
    "Aguardando peça",
}


EXTENSOES_PERMITIDAS = {
    "jpg",
    "jpeg",
    "png",
    "webp",
    "pdf",
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
        return Decimal("0")

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


def calcular_valor_total(
    valor_pecas,
    valor_mao_obra,
):
    return (
        valor_pecas + valor_mao_obra
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def buscar_veiculo(
    empresa_id,
    veiculo_id,
):
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


def buscar_obra(
    empresa_id,
    obra_id,
):
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


def salvar_comprovante(
    arquivo,
    empresa_id,
):
    if not arquivo or not arquivo.filename:
        return None

    nome_original = secure_filename(
        arquivo.filename
    )

    if not extensao_permitida(nome_original):
        raise ValueError(
            "O comprovante deve ser JPG, PNG, WEBP ou PDF."
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
        "manutencoes",
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
    tipo = (
        request.form
        .get("tipo", "")
        .strip()
    )

    descricao = (
        request.form
        .get("descricao", "")
        .strip()
    )

    fornecedor = (
        request.form
        .get("fornecedor", "")
        .strip()
    )

    data_entrada = converter_data(
        request.form.get("data_entrada")
    )

    data_saida = converter_data(
        request.form.get("data_saida")
    )

    km = converter_inteiro(
        request.form.get("km")
    )

    status = (
        request.form
        .get("status", "Agendada")
        .strip()
    )

    valor_pecas = converter_decimal(
        request.form.get("valor_pecas")
    )

    valor_mao_obra = converter_decimal(
        request.form.get("valor_mao_obra")
    )

    proxima_manutencao_data = converter_data(
        request.form.get(
            "proxima_manutencao_data"
        )
    )

    proxima_manutencao_km = converter_inteiro(
        request.form.get(
            "proxima_manutencao_km"
        )
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

    veiculo = buscar_veiculo(
        empresa_id,
        request.form.get("veiculo_id"),
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
        "tipo": tipo,
        "descricao": descricao,
        "fornecedor": fornecedor,
        "data_entrada": data_entrada,
        "data_saida": data_saida,
        "km": km,
        "status": status,
        "valor_pecas": valor_pecas,
        "valor_mao_obra": valor_mao_obra,
        "proxima_manutencao_data": (
            proxima_manutencao_data
        ),
        "proxima_manutencao_km": (
            proxima_manutencao_km
        ),
        "numero_nota": numero_nota,
        "observacoes": observacoes,
        "veiculo": veiculo,
        "obra": obra,
        "obra_id_informada": obra_id_informada,
    }


def validar_dados(dados):
    if dados["veiculo"] is None:
        return "Selecione um veículo válido."

    if dados["tipo"] not in TIPOS_PERMITIDOS:
        return "Selecione um tipo de manutenção válido."

    if not dados["descricao"]:
        return "Informe a descrição do serviço."

    if dados["data_entrada"] is None:
        return "Informe uma data de entrada válida."

    if dados["status"] not in STATUS_PERMITIDOS:
        return "Selecione um status válido."

    if dados["km"] is None or dados["km"] < 0:
        return "Informe uma quilometragem válida."

    if (
        dados["obra_id_informada"]
        and dados["obra"] is None
    ):
        return "A obra selecionada não foi encontrada."

    if dados["valor_pecas"] is None:
        return "Informe um valor válido para as peças."

    if dados["valor_mao_obra"] is None:
        return "Informe um valor válido para a mão de obra."

    if dados["valor_pecas"] < 0:
        return "O valor das peças não pode ser negativo."

    if dados["valor_mao_obra"] < 0:
        return (
            "O valor da mão de obra não pode ser negativo."
        )

    if (
        dados["data_saida"]
        and dados["data_saida"]
        < dados["data_entrada"]
    ):
        return (
            "A data de saída não pode ser anterior "
            "à data de entrada."
        )

    if (
        dados["status"] == "Concluída"
        and dados["data_saida"] is None
    ):
        return (
            "Informe a data de saída para concluir "
            "a manutenção."
        )

    if (
        dados["proxima_manutencao_km"] is not None
        and dados["proxima_manutencao_km"]
        <= dados["km"]
    ):
        return (
            "A KM da próxima manutenção precisa ser "
            "maior que a KM atual."
        )

    return None


def manutencao_duplicada(
    empresa_id,
    dados,
    manutencao_id=None,
):
    consulta = Manutencao.query.filter(
        Manutencao.empresa_id == empresa_id,
        Manutencao.veiculo_id
        == dados["veiculo"].id,
        Manutencao.data_entrada
        == dados["data_entrada"],
        Manutencao.km == dados["km"],
        Manutencao.descricao
        == dados["descricao"],
    )

    if manutencao_id is not None:
        consulta = consulta.filter(
            Manutencao.id != manutencao_id
        )

    return consulta.first()


def recalcular_status_veiculo(veiculo):
    possui_manutencao_aberta = (
        Manutencao.query
        .filter(
            Manutencao.empresa_id
            == veiculo.empresa_id,
            Manutencao.veiculo_id
            == veiculo.id,
            Manutencao.status.in_(
                STATUS_VEICULO_EM_MANUTENCAO
            ),
        )
        .first()
        is not None
    )

    if possui_manutencao_aberta:
        veiculo.status = "Em manutenção"

    elif veiculo.status == "Em manutenção":
        veiculo.status = "Ativo"


@manutencoes_bp.route("/manutencoes")
@login_required
def listar_manutencoes():
    empresa = current_user.empresa

    veiculos = (
        Veiculo.query
        .filter_by(empresa_id=empresa.id)
        .order_by(Veiculo.placa.asc())
        .all()
    )

    obras = (
        Obra.query
        .filter_by(empresa_id=empresa.id)
        .order_by(Obra.nome.asc())
        .all()
    )

    consulta = Manutencao.query.filter_by(
        empresa_id=empresa.id
    )

    veiculo_filtro = request.args.get(
        "veiculo_id",
        type=int,
    )

    obra_filtro = request.args.get(
        "obra_id",
        type=int,
    )

    tipo_filtro = (
        request.args
        .get("tipo", "")
        .strip()
    )

    status_filtro = (
        request.args
        .get("status", "")
        .strip()
    )

    data_inicio_filtro = converter_data(
        request.args.get("data_inicio")
    )

    data_fim_filtro = converter_data(
        request.args.get("data_fim")
    )

    if veiculo_filtro:
        consulta = consulta.filter(
            Manutencao.veiculo_id
            == veiculo_filtro
        )

    if obra_filtro:
        consulta = consulta.filter(
            Manutencao.obra_id
            == obra_filtro
        )

    if tipo_filtro in TIPOS_PERMITIDOS:
        consulta = consulta.filter(
            Manutencao.tipo == tipo_filtro
        )

    if status_filtro in STATUS_PERMITIDOS:
        consulta = consulta.filter(
            Manutencao.status == status_filtro
        )

    if data_inicio_filtro:
        consulta = consulta.filter(
            Manutencao.data_entrada
            >= data_inicio_filtro
        )

    if data_fim_filtro:
        consulta = consulta.filter(
            Manutencao.data_entrada
            <= data_fim_filtro
        )

    manutencoes = (
        consulta
        .order_by(
            Manutencao.data_entrada.desc(),
            Manutencao.id.desc(),
        )
        .all()
    )

    todas_manutencoes = (
        Manutencao.query
        .filter_by(empresa_id=empresa.id)
        .all()
    )

    total_em_andamento = sum(
        1
        for manutencao in todas_manutencoes
        if manutencao.status in {
            "Em andamento",
            "Aguardando peça",
        }
    )

    total_concluidas = sum(
        1
        for manutencao in todas_manutencoes
        if manutencao.status == "Concluída"
    )

    total_custo = sum(
        (
            manutencao.valor_total
            for manutencao in manutencoes
        ),
        Decimal("0"),
    )

    return render_template(
        "manutencoes.html",
        manutencoes=manutencoes,
        veiculos=veiculos,
        obras=obras,
        tipos=sorted(TIPOS_PERMITIDOS),
        status_permitidos=[
            "Agendada",
            "Em andamento",
            "Aguardando peça",
            "Concluída",
            "Cancelada",
        ],
        hoje=date.today().isoformat(),
        total_manutencoes=len(todas_manutencoes),
        total_em_andamento=total_em_andamento,
        total_concluidas=total_concluidas,
        total_custo=total_custo,
        veiculo_filtro=veiculo_filtro,
        obra_filtro=obra_filtro,
        tipo_filtro=tipo_filtro,
        status_filtro=status_filtro,
        data_inicio_filtro=request.args.get(
            "data_inicio",
            "",
        ),
        data_fim_filtro=request.args.get(
            "data_fim",
            "",
        ),
    )


@manutencoes_bp.route(
    "/manutencoes/nova",
    methods=["POST"],
)
@login_required
def nova_manutencao():
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
                "manutencoes.listar_manutencoes"
            )
        )

    if manutencao_duplicada(
        empresa.id,
        dados,
    ):
        flash(
            "Já existe uma manutenção semelhante "
            "para este veículo.",
            "warning",
        )

        return redirect(
            url_for(
                "manutencoes.listar_manutencoes"
            )
        )

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
                "manutencoes.listar_manutencoes"
            )
        )

    valor_total = calcular_valor_total(
        dados["valor_pecas"],
        dados["valor_mao_obra"],
    )

    manutencao = Manutencao(
        empresa_id=empresa.id,
        usuario_id=current_user.id,
        veiculo_id=dados["veiculo"].id,
        obra_id=(
            dados["obra"].id
            if dados["obra"]
            else None
        ),
        tipo=dados["tipo"],
        descricao=dados["descricao"],
        fornecedor=(
            dados["fornecedor"]
            or None
        ),
        data_entrada=dados["data_entrada"],
        data_saida=dados["data_saida"],
        km=dados["km"],
        status=dados["status"],
        valor_pecas=dados["valor_pecas"],
        valor_mao_obra=(
            dados["valor_mao_obra"]
        ),
        valor_total=valor_total,
        proxima_manutencao_data=(
            dados["proxima_manutencao_data"]
        ),
        proxima_manutencao_km=(
            dados["proxima_manutencao_km"]
        ),
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

    db.session.add(manutencao)
    db.session.flush()

    if dados["km"] > dados["veiculo"].km_atual:
        dados["veiculo"].km_atual = dados["km"]

    recalcular_status_veiculo(
        dados["veiculo"]
    )

    db.session.commit()

    flash(
        "Manutenção cadastrada com sucesso.",
        "success",
    )

    return redirect(
        url_for(
            "manutencoes.listar_manutencoes"
        )
    )


@manutencoes_bp.route(
    "/manutencoes/<int:manutencao_id>/editar",
    methods=["POST"],
)
@login_required
def editar_manutencao(manutencao_id):
    empresa = current_user.empresa

    manutencao = (
        Manutencao.query
        .filter_by(
            id=manutencao_id,
            empresa_id=empresa.id,
        )
        .first()
    )

    if manutencao is None:
        abort(404)

    veiculo_anterior = manutencao.veiculo

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
                "manutencoes.listar_manutencoes"
            )
        )

    if manutencao_duplicada(
        empresa.id,
        dados,
        manutencao_id=manutencao.id,
    ):
        flash(
            "Já existe outra manutenção semelhante "
            "para este veículo.",
            "warning",
        )

        return redirect(
            url_for(
                "manutencoes.listar_manutencoes"
            )
        )

    try:
        novo_comprovante = salvar_comprovante(
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
                "manutencoes.listar_manutencoes"
            )
        )

    comprovante_anterior = (
        manutencao.comprovante
    )

    manutencao.veiculo_id = (
        dados["veiculo"].id
    )

    manutencao.obra_id = (
        dados["obra"].id
        if dados["obra"]
        else None
    )

    manutencao.tipo = dados["tipo"]

    manutencao.descricao = (
        dados["descricao"]
    )

    manutencao.fornecedor = (
        dados["fornecedor"]
        or None
    )

    manutencao.data_entrada = (
        dados["data_entrada"]
    )

    manutencao.data_saida = (
        dados["data_saida"]
    )

    manutencao.km = dados["km"]
    manutencao.status = dados["status"]

    manutencao.valor_pecas = (
        dados["valor_pecas"]
    )

    manutencao.valor_mao_obra = (
        dados["valor_mao_obra"]
    )

    manutencao.valor_total = (
        calcular_valor_total(
            dados["valor_pecas"],
            dados["valor_mao_obra"],
        )
    )

    manutencao.proxima_manutencao_data = (
        dados["proxima_manutencao_data"]
    )

    manutencao.proxima_manutencao_km = (
        dados["proxima_manutencao_km"]
    )

    manutencao.numero_nota = (
        dados["numero_nota"]
        or None
    )

    manutencao.observacoes = (
        dados["observacoes"]
        or None
    )

    if novo_comprovante:
        manutencao.comprovante = (
            novo_comprovante
        )

    if dados["km"] > dados["veiculo"].km_atual:
        dados["veiculo"].km_atual = dados["km"]

    db.session.flush()

    recalcular_status_veiculo(
        veiculo_anterior
    )

    if (
        dados["veiculo"].id
        != veiculo_anterior.id
    ):
        recalcular_status_veiculo(
            dados["veiculo"]
        )

    db.session.commit()

    if (
        novo_comprovante
        and comprovante_anterior
        and comprovante_anterior
        != novo_comprovante
    ):
        remover_comprovante(
            comprovante_anterior
        )

    flash(
        "Manutenção atualizada com sucesso.",
        "success",
    )

    return redirect(
        url_for(
            "manutencoes.listar_manutencoes"
        )
    )