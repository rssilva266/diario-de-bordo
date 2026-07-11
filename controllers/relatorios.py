from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from xml.sax.saxutils import escape

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from database.models import (
    Abastecimento,
    DiarioBordo,
    Manutencao,
    Motorista,
    Obra,
    Veiculo,
)


relatorios_bp = Blueprint(
    "relatorios",
    __name__,
)


TIPOS_CUSTO_PERMITIDOS = {
    "",
    "Combustível",
    "Manutenção",
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


def decimal_zero(valor):
    if valor is None:
        return Decimal("0")

    if isinstance(valor, Decimal):
        return valor

    return Decimal(str(valor))


def dividir_decimal(
    dividendo,
    divisor,
    casas="0.01",
):
    if not divisor:
        return Decimal("0")

    return (
        decimal_zero(dividendo)
        / decimal_zero(divisor)
    ).quantize(
        Decimal(casas),
        rounding=ROUND_HALF_UP,
    )


def iterar_meses(data_inicio, data_fim):
    meses = []
    atual = data_inicio.replace(day=1)
    limite = data_fim.replace(day=1)

    while atual <= limite:
        meses.append(atual)

        if atual.month == 12:
            atual = atual.replace(
                year=atual.year + 1,
                month=1,
            )
        else:
            atual = atual.replace(
                month=atual.month + 1,
            )

    return meses


def adicionar_valores_resumo(
    resumo,
    chave,
    nome,
    codigo=None,
):
    if chave not in resumo:
        resumo[chave] = {
            "chave": chave,
            "codigo": codigo,
            "nome": nome,
            "km": 0,
            "litros": Decimal("0"),
            "combustivel": Decimal("0"),
            "manutencao": Decimal("0"),
            "total": Decimal("0"),
            "custo_km": Decimal("0"),
            "abastecimentos": 0,
            "manutencoes": 0,
            "diarios": 0,
        }

    return resumo[chave]


def localizar_por_id(lista, identificador):
    if not identificador:
        return None

    return next(
        (
            item
            for item in lista
            if item.id == identificador
        ),
        None,
    )


def formatar_moeda(valor):
    numero = decimal_zero(valor)

    return (
        f"R$ {numero:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def formatar_numero(valor, casas=0):
    numero = decimal_zero(valor)
    formatado = f"{numero:,.{casas}f}"

    return (
        formatado
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def montar_dados_relatorio(
    empresa,
    avisar_periodo_invalido=False,
):
    hoje = date.today()

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

    data_inicio = converter_data(
        request.args.get("data_inicio")
    )

    data_fim = converter_data(
        request.args.get("data_fim")
    )

    if data_inicio is None:
        data_inicio = hoje.replace(day=1)

    if data_fim is None:
        data_fim = hoje

    if data_fim < data_inicio:
        if avisar_periodo_invalido:
            flash(
                "A data final não pode ser anterior "
                "à data inicial. O período foi redefinido.",
                "warning",
            )

        data_inicio = hoje.replace(day=1)
        data_fim = hoje

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

    tipo_custo_filtro = (
        request.args
        .get("tipo_custo", "")
        .strip()
    )

    if (
        tipo_custo_filtro
        not in TIPOS_CUSTO_PERMITIDOS
    ):
        tipo_custo_filtro = ""

    abastecimentos = []

    if tipo_custo_filtro != "Manutenção":
        consulta_abastecimentos = (
            Abastecimento.query
            .filter(
                Abastecimento.empresa_id
                == empresa.id,
                Abastecimento.data
                >= data_inicio,
                Abastecimento.data
                <= data_fim,
            )
        )

        if veiculo_filtro:
            consulta_abastecimentos = (
                consulta_abastecimentos.filter(
                    Abastecimento.veiculo_id
                    == veiculo_filtro
                )
            )

        if motorista_filtro:
            consulta_abastecimentos = (
                consulta_abastecimentos.filter(
                    Abastecimento.motorista_id
                    == motorista_filtro
                )
            )

        if obra_filtro:
            consulta_abastecimentos = (
                consulta_abastecimentos.filter(
                    Abastecimento.obra_id
                    == obra_filtro
                )
            )

        abastecimentos = (
            consulta_abastecimentos
            .order_by(
                Abastecimento.data.asc(),
                Abastecimento.id.asc(),
            )
            .all()
        )

    manutencoes = []

    # Manutenções não têm vínculo direto com motorista.
    # Quando esse filtro está ativo, elas ficam fora
    # do consolidado para evitar atribuição incorreta.
    if (
        tipo_custo_filtro != "Combustível"
        and not motorista_filtro
    ):
        consulta_manutencoes = (
            Manutencao.query
            .filter(
                Manutencao.empresa_id
                == empresa.id,
                Manutencao.data_entrada
                >= data_inicio,
                Manutencao.data_entrada
                <= data_fim,
            )
        )

        if veiculo_filtro:
            consulta_manutencoes = (
                consulta_manutencoes.filter(
                    Manutencao.veiculo_id
                    == veiculo_filtro
                )
            )

        if obra_filtro:
            consulta_manutencoes = (
                consulta_manutencoes.filter(
                    Manutencao.obra_id
                    == obra_filtro
                )
            )

        manutencoes = (
            consulta_manutencoes
            .order_by(
                Manutencao.data_entrada.asc(),
                Manutencao.id.asc(),
            )
            .all()
        )

    consulta_diarios = (
        DiarioBordo.query
        .filter(
            DiarioBordo.empresa_id
            == empresa.id,
            DiarioBordo.data
            >= data_inicio,
            DiarioBordo.data
            <= data_fim,
        )
    )

    if veiculo_filtro:
        consulta_diarios = (
            consulta_diarios.filter(
                DiarioBordo.veiculo_id
                == veiculo_filtro
            )
        )

    if motorista_filtro:
        consulta_diarios = (
            consulta_diarios.filter(
                DiarioBordo.motorista_id
                == motorista_filtro
            )
        )

    if obra_filtro:
        consulta_diarios = (
            consulta_diarios.filter(
                DiarioBordo.obra_id
                == obra_filtro
            )
        )

    diarios = (
        consulta_diarios
        .order_by(
            DiarioBordo.data.asc(),
            DiarioBordo.id.asc(),
        )
        .all()
    )

    total_combustivel = sum(
        (
            decimal_zero(item.valor_total)
            for item in abastecimentos
        ),
        Decimal("0"),
    )

    total_manutencao = sum(
        (
            decimal_zero(item.valor_total)
            for item in manutencoes
        ),
        Decimal("0"),
    )

    total_custos = (
        total_combustivel
        + total_manutencao
    )

    total_litros = sum(
        (
            decimal_zero(item.litros)
            for item in abastecimentos
        ),
        Decimal("0"),
    )

    total_km = sum(
        (
            diario.km_percorrida or 0
            for diario in diarios
        ),
        0,
    )

    custo_por_km = dividir_decimal(
        total_custos,
        total_km,
    )

    preco_medio_litro = dividir_decimal(
        total_combustivel,
        total_litros,
        casas="0.001",
    )

    resumo_veiculos = {}

    veiculos_relatorio = veiculos

    if veiculo_filtro:
        veiculos_relatorio = [
            veiculo
            for veiculo in veiculos
            if veiculo.id == veiculo_filtro
        ]

    for veiculo in veiculos_relatorio:
        adicionar_valores_resumo(
            resumo=resumo_veiculos,
            chave=veiculo.id,
            codigo=veiculo.placa,
            nome=veiculo.modelo,
        )

    for abastecimento in abastecimentos:
        item = adicionar_valores_resumo(
            resumo=resumo_veiculos,
            chave=abastecimento.veiculo.id,
            codigo=abastecimento.veiculo.placa,
            nome=abastecimento.veiculo.modelo,
        )

        item["litros"] += decimal_zero(
            abastecimento.litros
        )

        item["combustivel"] += decimal_zero(
            abastecimento.valor_total
        )

        item["abastecimentos"] += 1

    for manutencao in manutencoes:
        item = adicionar_valores_resumo(
            resumo=resumo_veiculos,
            chave=manutencao.veiculo.id,
            codigo=manutencao.veiculo.placa,
            nome=manutencao.veiculo.modelo,
        )

        item["manutencao"] += decimal_zero(
            manutencao.valor_total
        )

        item["manutencoes"] += 1

    for diario in diarios:
        item = adicionar_valores_resumo(
            resumo=resumo_veiculos,
            chave=diario.veiculo.id,
            codigo=diario.veiculo.placa,
            nome=diario.veiculo.modelo,
        )

        item["km"] += diario.km_percorrida or 0
        item["diarios"] += 1

    for item in resumo_veiculos.values():
        item["total"] = (
            item["combustivel"]
            + item["manutencao"]
        )

        item["custo_km"] = dividir_decimal(
            item["total"],
            item["km"],
        )

    resumo_veiculos_lista = sorted(
        resumo_veiculos.values(),
        key=lambda item: item["total"],
        reverse=True,
    )

    resumo_obras = {}

    for abastecimento in abastecimentos:
        if abastecimento.obra:
            chave = abastecimento.obra.id
            codigo = abastecimento.obra.codigo
            nome = abastecimento.obra.nome
        else:
            chave = 0
            codigo = "-"
            nome = "Sem obra vinculada"

        item = adicionar_valores_resumo(
            resumo=resumo_obras,
            chave=chave,
            codigo=codigo,
            nome=nome,
        )

        item["litros"] += decimal_zero(
            abastecimento.litros
        )

        item["combustivel"] += decimal_zero(
            abastecimento.valor_total
        )

        item["abastecimentos"] += 1

    for manutencao in manutencoes:
        if manutencao.obra:
            chave = manutencao.obra.id
            codigo = manutencao.obra.codigo
            nome = manutencao.obra.nome
        else:
            chave = 0
            codigo = "-"
            nome = "Sem obra vinculada"

        item = adicionar_valores_resumo(
            resumo=resumo_obras,
            chave=chave,
            codigo=codigo,
            nome=nome,
        )

        item["manutencao"] += decimal_zero(
            manutencao.valor_total
        )

        item["manutencoes"] += 1

    for diario in diarios:
        if diario.obra:
            chave = diario.obra.id
            codigo = diario.obra.codigo
            nome = diario.obra.nome
        else:
            chave = 0
            codigo = "-"
            nome = "Sem obra vinculada"

        item = adicionar_valores_resumo(
            resumo=resumo_obras,
            chave=chave,
            codigo=codigo,
            nome=nome,
        )

        item["km"] += diario.km_percorrida or 0
        item["diarios"] += 1

    for item in resumo_obras.values():
        item["total"] = (
            item["combustivel"]
            + item["manutencao"]
        )

        item["custo_km"] = dividir_decimal(
            item["total"],
            item["km"],
        )

    resumo_obras_lista = sorted(
        resumo_obras.values(),
        key=lambda item: item["total"],
        reverse=True,
    )

    meses = iterar_meses(
        data_inicio,
        data_fim,
    )

    custos_mensais = {
        (
            mes.year,
            mes.month,
        ): {
            "combustivel": Decimal("0"),
            "manutencao": Decimal("0"),
        }
        for mes in meses
    }

    for abastecimento in abastecimentos:
        chave_mes = (
            abastecimento.data.year,
            abastecimento.data.month,
        )

        if chave_mes in custos_mensais:
            custos_mensais[chave_mes][
                "combustivel"
            ] += decimal_zero(
                abastecimento.valor_total
            )

    for manutencao in manutencoes:
        chave_mes = (
            manutencao.data_entrada.year,
            manutencao.data_entrada.month,
        )

        if chave_mes in custos_mensais:
            custos_mensais[chave_mes][
                "manutencao"
            ] += decimal_zero(
                manutencao.valor_total
            )

    grafico_meses = [
        mes.strftime("%m/%Y")
        for mes in meses
    ]

    grafico_combustivel = [
        float(
            custos_mensais[
                (mes.year, mes.month)
            ]["combustivel"]
        )
        for mes in meses
    ]

    grafico_manutencao = [
        float(
            custos_mensais[
                (mes.year, mes.month)
            ]["manutencao"]
        )
        for mes in meses
    ]

    ranking_veiculos = [
        item
        for item in resumo_veiculos_lista
        if item["total"] > 0
    ][:8]

    grafico_veiculos_labels = [
        item["codigo"]
        for item in ranking_veiculos
    ]

    grafico_veiculos_valores = [
        float(item["total"])
        for item in ranking_veiculos
    ]

    insights = []

    if resumo_veiculos_lista and total_custos > 0:
        veiculo_maior_custo = (
            resumo_veiculos_lista[0]
        )

        participacao = dividir_decimal(
            veiculo_maior_custo["total"]
            * Decimal("100"),
            total_custos,
            casas="0.1",
        )

        insights.append({
            "tipo": "informacao",
            "icone": "bi-graph-up-arrow",
            "titulo": "Maior custo da frota",
            "texto": (
                f"O veículo "
                f"{veiculo_maior_custo['codigo']} "
                f"representa {participacao}% dos "
                f"custos no período."
            ),
        })

    if total_manutencao > total_combustivel:
        insights.append({
            "tipo": "alerta",
            "icone": "bi-tools",
            "titulo": (
                "Manutenção acima do combustível"
            ),
            "texto": (
                "Os gastos com manutenção estão acima "
                "dos gastos com combustível no período."
            ),
        })

    limite_cnh = hoje + timedelta(days=30)

    motoristas_cnh_alerta = (
        Motorista.query
        .filter(
            Motorista.empresa_id == empresa.id,
            Motorista.status == "Ativo",
            Motorista.validade_cnh <= limite_cnh,
        )
        .count()
    )

    if motoristas_cnh_alerta:
        insights.append({
            "tipo": "alerta",
            "icone": "bi-person-vcard",
            "titulo": "Atenção às CNHs",
            "texto": (
                f"{motoristas_cnh_alerta} motorista(s) "
                f"possui(em) CNH vencida ou vencendo "
                f"nos próximos 30 dias."
            ),
        })

    todas_manutencoes = (
        Manutencao.query
        .filter_by(empresa_id=empresa.id)
        .all()
    )

    veiculos_proximos_manutencao = set()

    for manutencao in todas_manutencoes:
        manutencao_por_data = (
            manutencao.proxima_manutencao_data
            and manutencao.proxima_manutencao_data
            <= hoje + timedelta(days=30)
        )

        manutencao_por_km = (
            manutencao.proxima_manutencao_km
            and manutencao.veiculo
            and manutencao.proxima_manutencao_km
            <= manutencao.veiculo.km_atual + 1000
        )

        if manutencao_por_data or manutencao_por_km:
            veiculos_proximos_manutencao.add(
                manutencao.veiculo_id
            )

    if veiculos_proximos_manutencao:
        insights.append({
            "tipo": "alerta",
            "icone": "bi-wrench-adjustable",
            "titulo": "Manutenções próximas",
            "texto": (
                f"{len(veiculos_proximos_manutencao)} "
                f"veículo(s) está(ão) próximo(s) da "
                f"manutenção programada."
            ),
        })

    limite_sem_movimento = (
        hoje - timedelta(days=15)
    )

    ultimas_movimentacoes = {}

    diarios_empresa = (
        DiarioBordo.query
        .filter_by(empresa_id=empresa.id)
        .order_by(DiarioBordo.data.desc())
        .all()
    )

    for diario in diarios_empresa:
        if diario.veiculo_id not in ultimas_movimentacoes:
            ultimas_movimentacoes[
                diario.veiculo_id
            ] = diario.data

    veiculos_sem_movimento = [
        veiculo
        for veiculo in veiculos
        if (
            veiculo.status == "Ativo"
            and (
                veiculo.id
                not in ultimas_movimentacoes
                or ultimas_movimentacoes[
                    veiculo.id
                ] < limite_sem_movimento
            )
        )
    ]

    if veiculos_sem_movimento:
        insights.append({
            "tipo": "informacao",
            "icone": "bi-pause-circle",
            "titulo": "Veículos sem movimentação",
            "texto": (
                f"{len(veiculos_sem_movimento)} "
                f"veículo(s) ativo(s) não possui(em) "
                f"diário de bordo nos últimos 15 dias."
            ),
        })

    if not insights:
        insights.append({
            "tipo": "sucesso",
            "icone": "bi-check-circle",
            "titulo": (
                "Operação sem alertas relevantes"
            ),
            "texto": (
                "Nenhuma anomalia importante foi "
                "identificada com os dados disponíveis."
            ),
        })

    veiculo_selecionado = localizar_por_id(
        veiculos,
        veiculo_filtro,
    )

    motorista_selecionado = localizar_por_id(
        motoristas,
        motorista_filtro,
    )

    obra_selecionada = localizar_por_id(
        obras,
        obra_filtro,
    )

    filtros_pdf = [
        (
            "Período",
            f"{data_inicio.strftime('%d/%m/%Y')} "
            f"a {data_fim.strftime('%d/%m/%Y')}",
        ),
        (
            "Veículo",
            (
                f"{veiculo_selecionado.placa} - "
                f"{veiculo_selecionado.modelo}"
                if veiculo_selecionado
                else "Todos"
            ),
        ),
        (
            "Motorista",
            (
                motorista_selecionado.nome
                if motorista_selecionado
                else "Todos"
            ),
        ),
        (
            "Obra",
            (
                f"{obra_selecionada.codigo} - "
                f"{obra_selecionada.nome}"
                if obra_selecionada
                else "Todas"
            ),
        ),
        (
            "Tipo de custo",
            tipo_custo_filtro or "Todos",
        ),
    ]

    return {
        "empresa": empresa,
        "veiculos": veiculos,
        "motoristas": motoristas,
        "obras": obras,
        "data_inicio": data_inicio.isoformat(),
        "data_fim": data_fim.isoformat(),
        "data_inicio_obj": data_inicio,
        "data_fim_obj": data_fim,
        "veiculo_filtro": veiculo_filtro,
        "motorista_filtro": motorista_filtro,
        "obra_filtro": obra_filtro,
        "tipo_custo_filtro": tipo_custo_filtro,
        "total_combustivel": total_combustivel,
        "total_manutencao": total_manutencao,
        "total_custos": total_custos,
        "total_litros": total_litros,
        "total_km": total_km,
        "custo_por_km": custo_por_km,
        "preco_medio_litro": preco_medio_litro,
        "total_abastecimentos": len(abastecimentos),
        "total_manutencoes": len(manutencoes),
        "total_diarios": len(diarios),
        "resumo_veiculos": resumo_veiculos_lista,
        "resumo_obras": resumo_obras_lista,
        "insights": insights,
        "grafico_meses": grafico_meses,
        "grafico_combustivel": grafico_combustivel,
        "grafico_manutencao": grafico_manutencao,
        "grafico_veiculos_labels": (
            grafico_veiculos_labels
        ),
        "grafico_veiculos_valores": (
            grafico_veiculos_valores
        ),
        "filtros_pdf": filtros_pdf,
        "motorista_filtrado": bool(
            motorista_filtro
        ),
    }


def gerar_pdf_relatorio(dados):
    try:
        from reportlab.lib import colors
        from reportlab.lib.colors import HexColor
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import (
            ParagraphStyle,
            getSampleStyleSheet,
        )
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ModuleNotFoundError as erro:
        raise RuntimeError(
            "A biblioteca ReportLab não está instalada."
        ) from erro

    buffer = BytesIO()
    pagina = landscape(A4)

    documento = SimpleDocTemplate(
        buffer,
        pagesize=pagina,
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=17 * mm,
        bottomMargin=12 * mm,
        title="Relatório consolidado da frota",
        author="MSM Fleet Manager",
    )

    estilos_base = getSampleStyleSheet()

    estilo_titulo = ParagraphStyle(
        "TituloRelatorio",
        parent=estilos_base["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=HexColor("#0F172A"),
        alignment=TA_LEFT,
        spaceAfter=5,
    )

    estilo_subtitulo = ParagraphStyle(
        "SubtituloRelatorio",
        parent=estilos_base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=HexColor("#475569"),
        spaceAfter=8,
    )

    estilo_secao = ParagraphStyle(
        "SecaoRelatorio",
        parent=estilos_base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=HexColor("#0F172A"),
        spaceBefore=7,
        spaceAfter=5,
    )

    estilo_texto = ParagraphStyle(
        "TextoRelatorio",
        parent=estilos_base["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=HexColor("#334155"),
    )

    estilo_texto_central = ParagraphStyle(
        "TextoCentralRelatorio",
        parent=estilo_texto,
        alignment=TA_CENTER,
    )

    estilo_cabecalho_tabela = ParagraphStyle(
        "CabecalhoTabelaRelatorio",
        parent=estilo_texto,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        alignment=TA_CENTER,
    )

    empresa = dados["empresa"]
    nome_empresa = (
        empresa.nome_fantasia
        or empresa.razao_social
        or "Empresa"
    )

    identificacao_empresa = empresa.razao_social

    if empresa.cnpj:
        identificacao_empresa += (
            f" | CNPJ: {empresa.cnpj}"
        )

    elementos = [
        Paragraph(
            "Relatório consolidado da frota",
            estilo_titulo,
        ),
        Paragraph(
            escape(identificacao_empresa),
            estilo_subtitulo,
        ),
    ]

    dados_filtros = []

    for indice in range(0, len(dados["filtros_pdf"]), 2):
        linha = []

        for rotulo, valor in dados["filtros_pdf"][
            indice:indice + 2
        ]:
            linha.append(
                Paragraph(
                    f"<b>{escape(rotulo)}:</b> "
                    f"{escape(str(valor))}",
                    estilo_texto,
                )
            )

        while len(linha) < 2:
            linha.append("")

        dados_filtros.append(linha)

    tabela_filtros = Table(
        dados_filtros,
        colWidths=[128 * mm, 128 * mm],
    )

    tabela_filtros.setStyle(TableStyle([
        (
            "BACKGROUND",
            (0, 0),
            (-1, -1),
            HexColor("#F8FAFC"),
        ),
        (
            "BOX",
            (0, 0),
            (-1, -1),
            0.5,
            HexColor("#CBD5E1"),
        ),
        (
            "INNERGRID",
            (0, 0),
            (-1, -1),
            0.25,
            HexColor("#E2E8F0"),
        ),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    elementos.extend([
        tabela_filtros,
        Spacer(1, 6 * mm),
        Paragraph(
            "Resumo executivo",
            estilo_secao,
        ),
    ])

    resumo_executivo = [
        [
            Paragraph(
                "Combustível",
                estilo_cabecalho_tabela,
            ),
            Paragraph(
                "Manutenção",
                estilo_cabecalho_tabela,
            ),
            Paragraph(
                "Custo total",
                estilo_cabecalho_tabela,
            ),
            Paragraph(
                "Custo por KM",
                estilo_cabecalho_tabela,
            ),
        ],
        [
            Paragraph(
                formatar_moeda(
                    dados["total_combustivel"]
                ),
                estilo_texto_central,
            ),
            Paragraph(
                formatar_moeda(
                    dados["total_manutencao"]
                ),
                estilo_texto_central,
            ),
            Paragraph(
                formatar_moeda(
                    dados["total_custos"]
                ),
                estilo_texto_central,
            ),
            Paragraph(
                formatar_moeda(
                    dados["custo_por_km"]
                ),
                estilo_texto_central,
            ),
        ],
        [
            Paragraph(
                (
                    f"{dados['total_abastecimentos']} registros | "
                    f"{formatar_numero(dados['total_litros'], 3)} L"
                ),
                estilo_texto_central,
            ),
            Paragraph(
                f"{dados['total_manutencoes']} registros",
                estilo_texto_central,
            ),
            Paragraph(
                (
                    f"Preço médio: R$ "
                    f"{formatar_numero(dados['preco_medio_litro'], 3)}/L"
                ),
                estilo_texto_central,
            ),
            Paragraph(
                (
                    f"{formatar_numero(dados['total_km'], 0)} km | "
                    f"{dados['total_diarios']} diários"
                ),
                estilo_texto_central,
            ),
        ],
    ]

    tabela_resumo = Table(
        resumo_executivo,
        colWidths=[64 * mm] * 4,
    )

    tabela_resumo.setStyle(TableStyle([
        (
            "BACKGROUND",
            (0, 0),
            (-1, 0),
            HexColor("#0F172A"),
        ),
        (
            "BACKGROUND",
            (0, 1),
            (-1, -1),
            HexColor("#F8FAFC"),
        ),
        (
            "BOX",
            (0, 0),
            (-1, -1),
            0.5,
            HexColor("#CBD5E1"),
        ),
        (
            "INNERGRID",
            (0, 0),
            (-1, -1),
            0.25,
            HexColor("#CBD5E1"),
        ),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elementos.append(tabela_resumo)

    if dados["motorista_filtrado"]:
        elementos.extend([
            Spacer(1, 3 * mm),
            Paragraph(
                (
                    "Observação: manutenções não possuem "
                    "motorista vinculado e foram excluídas "
                    "do consolidado com este filtro."
                ),
                estilo_subtitulo,
            ),
        ])

    elementos.extend([
        Spacer(1, 3 * mm),
        Paragraph(
            "Fleet Intelligence",
            estilo_secao,
        ),
    ])

    dados_insights = []

    for insight in dados["insights"]:
        dados_insights.append([
            Paragraph(
                f"<b>{escape(insight['titulo'])}</b><br/>"
                f"{escape(insight['texto'])}",
                estilo_texto,
            )
        ])

    tabela_insights = Table(
        dados_insights,
        colWidths=[256 * mm],
    )

    tabela_insights.setStyle(TableStyle([
        (
            "BACKGROUND",
            (0, 0),
            (-1, -1),
            HexColor("#FFFBEB"),
        ),
        (
            "BOX",
            (0, 0),
            (-1, -1),
            0.5,
            HexColor("#F59E0B"),
        ),
        (
            "INNERGRID",
            (0, 0),
            (-1, -1),
            0.25,
            HexColor("#FDE68A"),
        ),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elementos.append(tabela_insights)

    elementos.extend([
        Spacer(1, 4 * mm),
        Paragraph(
            "Resumo por veículo",
            estilo_secao,
        ),
    ])

    cabecalho_veiculos = [
        "Placa",
        "Modelo",
        "KM",
        "Litros",
        "Combustível",
        "Manutenção",
        "Total",
        "Custo/KM",
    ]

    dados_veiculos = [[
        Paragraph(
            escape(titulo),
            estilo_cabecalho_tabela,
        )
        for titulo in cabecalho_veiculos
    ]]

    for item in dados["resumo_veiculos"]:
        dados_veiculos.append([
            Paragraph(
                escape(str(item["codigo"] or "-")),
                estilo_texto,
            ),
            Paragraph(
                escape(str(item["nome"] or "-")),
                estilo_texto,
            ),
            Paragraph(
                formatar_numero(item["km"], 0),
                estilo_texto_central,
            ),
            Paragraph(
                formatar_numero(item["litros"], 3),
                estilo_texto_central,
            ),
            Paragraph(
                formatar_moeda(item["combustivel"]),
                estilo_texto_central,
            ),
            Paragraph(
                formatar_moeda(item["manutencao"]),
                estilo_texto_central,
            ),
            Paragraph(
                formatar_moeda(item["total"]),
                estilo_texto_central,
            ),
            Paragraph(
                formatar_moeda(item["custo_km"]),
                estilo_texto_central,
            ),
        ])

    if len(dados_veiculos) == 1:
        dados_veiculos.append([
            Paragraph(
                "Nenhum veículo encontrado no período.",
                estilo_texto,
            ),
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ])

    tabela_veiculos = Table(
        dados_veiculos,
        repeatRows=1,
        colWidths=[
            23 * mm,
            48 * mm,
            23 * mm,
            25 * mm,
            34 * mm,
            34 * mm,
            34 * mm,
            35 * mm,
        ],
    )

    tabela_veiculos.setStyle(TableStyle([
        (
            "BACKGROUND",
            (0, 0),
            (-1, 0),
            HexColor("#0F172A"),
        ),
        (
            "ROWBACKGROUNDS",
            (0, 1),
            (-1, -1),
            [
                colors.white,
                HexColor("#F8FAFC"),
            ],
        ),
        (
            "GRID",
            (0, 0),
            (-1, -1),
            0.25,
            HexColor("#CBD5E1"),
        ),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    elementos.append(tabela_veiculos)

    elementos.extend([
        PageBreak(),
        Paragraph(
            "Resumo por obra",
            estilo_secao,
        ),
    ])

    cabecalho_obras = [
        "Código",
        "Obra",
        "KM",
        "Litros",
        "Combustível",
        "Manutenção",
        "Total",
        "Custo/KM",
    ]

    dados_obras = [[
        Paragraph(
            escape(titulo),
            estilo_cabecalho_tabela,
        )
        for titulo in cabecalho_obras
    ]]

    for item in dados["resumo_obras"]:
        dados_obras.append([
            Paragraph(
                escape(str(item["codigo"] or "-")),
                estilo_texto,
            ),
            Paragraph(
                escape(str(item["nome"] or "-")),
                estilo_texto,
            ),
            Paragraph(
                formatar_numero(item["km"], 0),
                estilo_texto_central,
            ),
            Paragraph(
                formatar_numero(item["litros"], 3),
                estilo_texto_central,
            ),
            Paragraph(
                formatar_moeda(item["combustivel"]),
                estilo_texto_central,
            ),
            Paragraph(
                formatar_moeda(item["manutencao"]),
                estilo_texto_central,
            ),
            Paragraph(
                formatar_moeda(item["total"]),
                estilo_texto_central,
            ),
            Paragraph(
                formatar_moeda(item["custo_km"]),
                estilo_texto_central,
            ),
        ])

    if len(dados_obras) == 1:
        dados_obras.append([
            Paragraph(
                "Nenhuma obra encontrada no período.",
                estilo_texto,
            ),
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ])

    tabela_obras = Table(
        dados_obras,
        repeatRows=1,
        colWidths=[
            27 * mm,
            65 * mm,
            23 * mm,
            25 * mm,
            34 * mm,
            34 * mm,
            34 * mm,
            34 * mm,
        ],
    )

    tabela_obras.setStyle(TableStyle([
        (
            "BACKGROUND",
            (0, 0),
            (-1, 0),
            HexColor("#0F172A"),
        ),
        (
            "ROWBACKGROUNDS",
            (0, 1),
            (-1, -1),
            [
                colors.white,
                HexColor("#F8FAFC"),
            ],
        ),
        (
            "GRID",
            (0, 0),
            (-1, -1),
            0.25,
            HexColor("#CBD5E1"),
        ),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    elementos.append(tabela_obras)

    emitido_em = datetime.now()

    elementos.extend([
        Spacer(1, 8 * mm),
        Paragraph(
            (
                "Relatório emitido em "
                f"{emitido_em.strftime('%d/%m/%Y às %H:%M')}."
            ),
            estilo_subtitulo,
        ),
    ])

    def desenhar_cabecalho_rodape(canvas, _documento):
        largura, altura = pagina

        canvas.saveState()
        canvas.setStrokeColor(HexColor("#CBD5E1"))
        canvas.setLineWidth(0.5)

        canvas.setFont(
            "Helvetica-Bold",
            8,
        )

        canvas.setFillColor(HexColor("#0F172A"))
        canvas.drawString(
            10 * mm,
            altura - 9 * mm,
            nome_empresa[:85],
        )

        canvas.line(
            10 * mm,
            altura - 11 * mm,
            largura - 10 * mm,
            altura - 11 * mm,
        )

        canvas.line(
            10 * mm,
            9 * mm,
            largura - 10 * mm,
            9 * mm,
        )

        canvas.setFont(
            "Helvetica",
            7,
        )

        canvas.setFillColor(HexColor("#64748B"))
        canvas.drawString(
            10 * mm,
            5.5 * mm,
            "MSM Fleet Manager",
        )

        canvas.drawRightString(
            largura - 10 * mm,
            5.5 * mm,
            f"Página {canvas.getPageNumber()}",
        )

        canvas.restoreState()

    documento.build(
        elementos,
        onFirstPage=desenhar_cabecalho_rodape,
        onLaterPages=desenhar_cabecalho_rodape,
    )

    buffer.seek(0)
    return buffer


@relatorios_bp.route("/relatorios")
@login_required
def listar_relatorios():
    dados = montar_dados_relatorio(
        current_user.empresa,
        avisar_periodo_invalido=True,
    )

    parametros_pdf = request.args.to_dict(
        flat=True
    )

    dados["url_pdf"] = url_for(
        "relatorios.exportar_pdf",
        **parametros_pdf,
    )

    return render_template(
        "relatorios.html",
        **dados,
    )


@relatorios_bp.route("/relatorios/exportar-pdf")
@login_required
def exportar_pdf():
    dados = montar_dados_relatorio(
        current_user.empresa,
    )

    try:
        arquivo_pdf = gerar_pdf_relatorio(
            dados
        )
    except RuntimeError as erro:
        flash(
            str(erro),
            "danger",
        )

        return redirect(
            url_for(
                "relatorios.listar_relatorios",
                **request.args.to_dict(flat=True),
            )
        )

    nome_arquivo = (
        "relatorio_frota_"
        f"{dados['data_inicio_obj'].strftime('%d-%m-%Y')}"
        "_a_"
        f"{dados['data_fim_obj'].strftime('%d-%m-%Y')}"
        ".pdf"
    )

    return send_file(
        arquivo_pdf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=nome_arquivo,
        max_age=0,
    )