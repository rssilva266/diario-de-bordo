from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from sqlalchemy.orm import joinedload, selectinload
from werkzeug.utils import secure_filename

from database.models import (
    Abastecimento,
    DiarioBordo,
    Motorista,
    MovimentacaoMaterial,
    Obra,
    Veiculo,
)
from extensions import db


diario_bp = Blueprint("diario", __name__)


EXTENSOES_IMAGEM = {"jpg", "jpeg", "png", "webp"}
STATUS_MOVIMENTACAO = {
    "Em trânsito",
    "Recebido",
    "Recebido com ressalva",
    "Cancelado",
}
FUSO_LOCAL = ZoneInfo("America/Rio_Branco")


def agora_local():
    return datetime.now(FUSO_LOCAL).replace(tzinfo=None)


def converter_data(valor):
    if not valor:
        return None

    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def converter_hora(valor):
    if not valor:
        return None

    try:
        return datetime.strptime(valor, "%H:%M").time()
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

    texto = str(valor).strip().replace("R$", "").replace(" ", "")

    if not texto:
        return None

    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError):
        return None


def calcular_valor_total(litros, valor_litro):
    return (litros * valor_litro).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def buscar_veiculo(empresa_id, veiculo_id):
    try:
        veiculo_id = int(veiculo_id)
    except (TypeError, ValueError):
        return None

    return Veiculo.query.filter_by(
        id=veiculo_id,
        empresa_id=empresa_id,
    ).first()


def buscar_motorista(empresa_id, motorista_id):
    try:
        motorista_id = int(motorista_id)
    except (TypeError, ValueError):
        return None

    return Motorista.query.filter_by(
        id=motorista_id,
        empresa_id=empresa_id,
    ).first()


def buscar_obra(empresa_id, obra_id):
    if not obra_id:
        return None

    try:
        obra_id = int(obra_id)
    except (TypeError, ValueError):
        return None

    return Obra.query.filter_by(
        id=obra_id,
        empresa_id=empresa_id,
    ).first()


def diario_aberto_do_veiculo(empresa_id, veiculo_id, diario_id=None):
    consulta = DiarioBordo.query.filter(
        DiarioBordo.empresa_id == empresa_id,
        DiarioBordo.veiculo_id == veiculo_id,
        DiarioBordo.status == "Em andamento",
    )

    if diario_id is not None:
        consulta = consulta.filter(DiarioBordo.id != diario_id)

    return consulta.first()


def diario_aberto_do_motorista(empresa_id, motorista_id, diario_id=None):
    consulta = DiarioBordo.query.filter(
        DiarioBordo.empresa_id == empresa_id,
        DiarioBordo.motorista_id == motorista_id,
        DiarioBordo.status == "Em andamento",
    )

    if diario_id is not None:
        consulta = consulta.filter(DiarioBordo.id != diario_id)

    return consulta.first()


def obter_dados_formulario(empresa_id, usar_veiculo_vinculado=False):
    motorista = buscar_motorista(
        empresa_id,
        request.form.get("motorista_id"),
    )

    if usar_veiculo_vinculado:
        veiculo = motorista.veiculo if motorista else None

        if veiculo and veiculo.empresa_id != empresa_id:
            veiculo = None
    else:
        veiculo = buscar_veiculo(
            empresa_id,
            request.form.get("veiculo_id"),
        )

    obra_id_informada = request.form.get("obra_id", "")
    obra = buscar_obra(empresa_id, obra_id_informada)

    return {
        "data": converter_data(request.form.get("data")),
        "hora_saida": converter_hora(request.form.get("hora_saida")),
        "km_inicial": converter_inteiro(request.form.get("km_inicial")),
        "origem": request.form.get("origem", "").strip(),
        "destino": request.form.get("destino", "").strip(),
        "finalidade": request.form.get("finalidade", "").strip(),
        "ocorrencias": request.form.get("ocorrencias", "").strip(),
        "veiculo": veiculo,
        "motorista": motorista,
        "obra": obra,
        "obra_id_informada": obra_id_informada,
    }


def validar_dados(
    dados,
    empresa_id,
    diario_id=None,
    verificar_diario_aberto=True,
    exigir_veiculo_vinculado=False,
):
    if dados["data"] is None:
        return "Informe uma data válida."

    if dados["hora_saida"] is None:
        return "Informe o horário de saída."

    if dados["motorista"] is None:
        return "Selecione um motorista válido."

    if dados["veiculo"] is None:
        if exigir_veiculo_vinculado:
            return (
                "O motorista selecionado não possui veículo vinculado. "
                "Atualize o cadastro do motorista antes de iniciar o diário."
            )

        return "Selecione um veículo válido."

    if (
        exigir_veiculo_vinculado
        and dados["motorista"].veiculo_id != dados["veiculo"].id
    ):
        return "O veículo informado não corresponde ao vínculo do motorista."

    if dados["obra_id_informada"] and dados["obra"] is None:
        return "A obra selecionada não foi encontrada."

    if dados["km_inicial"] is None:
        return "Informe a quilometragem inicial."

    if dados["km_inicial"] < 0:
        return "A quilometragem inicial não pode ser negativa."

    if not dados["origem"]:
        return "Informe a origem do deslocamento."

    if not dados["destino"]:
        return "Informe o destino do deslocamento."

    if verificar_diario_aberto:
        diario_veiculo = diario_aberto_do_veiculo(
            empresa_id,
            dados["veiculo"].id,
            diario_id,
        )

        if diario_veiculo:
            return (
                f"O veículo {dados['veiculo'].placa} já possui um diário "
                "de bordo em andamento. Finalize-o antes de iniciar outro."
            )

        diario_motorista = diario_aberto_do_motorista(
            empresa_id,
            dados["motorista"].id,
            diario_id,
        )

        if diario_motorista:
            return (
                f"O motorista {dados['motorista'].nome} já possui um diário "
                "de bordo em andamento. Finalize-o antes de iniciar outro."
            )

    return None


def obter_dados_abastecimento(veiculo):
    houve = request.form.get("houve_abastecimento") == "sim"

    return {
        "houve": houve,
        "posto": request.form.get("posto_abastecimento", "").strip(),
        "combustivel": (veiculo.combustivel or "").strip() if veiculo else "",
        "litros": converter_decimal(request.form.get("litros_abastecimento")),
        "valor_litro": converter_decimal(
            request.form.get("valor_litro_abastecimento")
        ),
        "numero_nota": request.form.get("numero_nota_abastecimento", "").strip(),
        "tanque_cheio": request.form.get("tanque_cheio_abastecimento") == "on",
        "foto_odometro": request.files.get("foto_odometro"),
        "cupom_fiscal": request.files.get("cupom_fiscal"),
    }


def obter_dados_material():
    transporta = request.form.get("transporta_material") == "sim"

    return {
        "transporta": transporta,
        "material": request.form.get("material", "").strip(),
        "numero_movimentacao": request.form.get(
            "numero_movimentacao",
            "",
        ).strip(),
        "quantidade": converter_decimal(request.form.get("quantidade_material")),
        "unidade": request.form.get("unidade_material", "").strip(),
        "observacao": request.form.get("observacao_material", "").strip(),
    }


def validar_material(dados):
    if not dados["transporta"]:
        return None

    if not dados["material"]:
        return "Informe o material transportado."

    if not dados["numero_movimentacao"]:
        return "Informe o número da movimentação."

    if dados["quantidade"] is not None and dados["quantidade"] <= 0:
        return "A quantidade do material deve ser maior que zero."

    if dados["quantidade"] is not None and not dados["unidade"]:
        return "Informe a unidade da quantidade transportada."

    if dados["unidade"] and dados["quantidade"] is None:
        return "Informe a quantidade do material ou deixe a unidade vazia."

    return None


def extensao_arquivo(arquivo):
    if not arquivo or not arquivo.filename:
        return None

    nome = secure_filename(arquivo.filename)

    if "." not in nome:
        return None

    return nome.rsplit(".", 1)[1].lower()


def validar_abastecimento(dados):
    if not dados["houve"]:
        return None

    if not dados["posto"]:
        return "Informe o posto ou fornecedor do abastecimento."

    if not dados["combustivel"]:
        return (
            "O veículo não possui tipo de combustível cadastrado. "
            "Atualize o veículo antes de registrar o abastecimento."
        )

    if dados["litros"] is None or dados["litros"] <= 0:
        return "A quantidade de litros deve ser maior que zero."

    if dados["valor_litro"] is None or dados["valor_litro"] <= 0:
        return "O valor por litro deve ser maior que zero."

    if not dados["foto_odometro"] or not dados["foto_odometro"].filename:
        return "Inclua a foto do odômetro."

    if extensao_arquivo(dados["foto_odometro"]) not in EXTENSOES_IMAGEM:
        return "A foto do odômetro deve ser JPG, PNG ou WEBP."

    if not dados["cupom_fiscal"] or not dados["cupom_fiscal"].filename:
        return "Inclua a foto da placa do veículo."

    if extensao_arquivo(dados["cupom_fiscal"]) not in EXTENSOES_IMAGEM:
        return "A foto da placa deve ser JPG, PNG ou WEBP."

    return None


def salvar_arquivo_abastecimento(arquivo, empresa_id, prefixo, extensoes):
    extensao = extensao_arquivo(arquivo)

    if extensao not in extensoes:
        raise ValueError("Formato de arquivo não permitido.")

    pasta_relativa = Path("uploads", "abastecimentos", str(empresa_id))
    pasta_absoluta = Path(current_app.static_folder) / pasta_relativa
    pasta_absoluta.mkdir(parents=True, exist_ok=True)

    nome_final = f"{prefixo}-{uuid4().hex}.{extensao}"
    arquivo.save(pasta_absoluta / nome_final)

    return (pasta_relativa / nome_final).as_posix()


def remover_arquivo(caminho_relativo):
    if not caminho_relativo:
        return

    pasta_static = Path(current_app.static_folder).resolve()
    caminho_absoluto = (pasta_static / caminho_relativo).resolve()

    try:
        caminho_absoluto.relative_to(pasta_static)
    except ValueError:
        return

    if caminho_absoluto.exists():
        caminho_absoluto.unlink()


def obter_filtros_diario():
    status = request.args.get("status", "").strip()

    if status not in ("Em andamento", "Concluído"):
        status = ""

    return {
        "status": status,
        "veiculo_id": request.args.get("veiculo_id", type=int),
        "motorista_id": request.args.get("motorista_id", type=int),
        "data_inicio": converter_data(request.args.get("data_inicio")),
        "data_fim": converter_data(request.args.get("data_fim")),
        "data_inicio_texto": request.args.get("data_inicio", ""),
        "data_fim_texto": request.args.get("data_fim", ""),
    }


def aplicar_filtros_diario(consulta, filtros):
    if filtros["status"]:
        consulta = consulta.filter(
            DiarioBordo.status == filtros["status"]
        )

    if filtros["veiculo_id"]:
        consulta = consulta.filter(
            DiarioBordo.veiculo_id == filtros["veiculo_id"]
        )

    if filtros["motorista_id"]:
        consulta = consulta.filter(
            DiarioBordo.motorista_id == filtros["motorista_id"]
        )

    if filtros["data_inicio"]:
        consulta = consulta.filter(
            DiarioBordo.data >= filtros["data_inicio"]
        )

    if filtros["data_fim"]:
        consulta = consulta.filter(
            DiarioBordo.data <= filtros["data_fim"]
        )

    return consulta


def formatar_decimal_br(valor, casas=2):
    if valor is None:
        return ""

    numero = Decimal(valor)
    texto = f"{numero:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_moeda_br(valor):
    if valor is None:
        return ""

    return f"R$ {formatar_decimal_br(valor, 2)}"


def limitar_texto_pdf(pdf, texto, largura, fonte, tamanho):
    texto = (
        str(texto or "")
        .replace("\n", " ")
        .encode("cp1252", errors="replace")
        .decode("cp1252")
        .strip()
    )

    if pdfmetrics.stringWidth(texto, fonte, tamanho) <= largura:
        return texto

    sufixo = "..."
    disponivel = max(largura - pdfmetrics.stringWidth(
        sufixo,
        fonte,
        tamanho,
    ), 0)

    while texto and pdfmetrics.stringWidth(
        texto,
        fonte,
        tamanho,
    ) > disponivel:
        texto = texto[:-1]

    return texto.rstrip() + sufixo


def desenhar_texto_celula(
    pdf,
    texto,
    x,
    y,
    largura,
    altura,
    tamanho=7,
    negrito=False,
    alinhamento="center",
    padding=2,
):
    fonte = "Helvetica-Bold" if negrito else "Helvetica"
    texto = limitar_texto_pdf(
        pdf,
        texto,
        max(largura - padding * 2, 1),
        fonte,
        tamanho,
    )
    pdf.setFont(fonte, tamanho)
    pdf.setFillColor(colors.black)
    linha_base = y + (altura - tamanho) / 2 + 1.2

    if alinhamento == "left":
        pdf.drawString(x + padding, linha_base, texto)
    elif alinhamento == "right":
        pdf.drawRightString(x + largura - padding, linha_base, texto)
    else:
        pdf.drawCentredString(x + largura / 2, linha_base, texto)


def desenhar_campo_identificacao(
    pdf,
    rotulo,
    valor,
    x,
    y,
    largura,
    altura,
    largura_rotulo,
):
    pdf.setLineWidth(0.8)
    pdf.rect(x, y, largura, altura, stroke=1, fill=0)
    desenhar_texto_celula(
        pdf,
        rotulo,
        x,
        y,
        largura_rotulo,
        altura,
        tamanho=8,
        negrito=True,
        alinhamento="left",
    )
    desenhar_texto_celula(
        pdf,
        valor,
        x + largura_rotulo,
        y,
        largura - largura_rotulo,
        altura,
        tamanho=8,
        negrito=True,
        alinhamento="left",
    )


def dados_linha_diario(diario):
    abastecimentos = list(diario.abastecimentos or [])
    houve_abastecimento = bool(abastecimentos)
    litros = sum(
        (Decimal(item.litros or 0) for item in abastecimentos),
        Decimal("0"),
    )
    valor_total = sum(
        (Decimal(item.valor_total or 0) for item in abastecimentos),
        Decimal("0"),
    )

    observacoes = [f"{diario.origem} - {diario.destino}"]

    if diario.finalidade:
        observacoes.append(diario.finalidade)

    if diario.ocorrencias:
        observacoes.append(diario.ocorrencias)

    if diario.status == "Em andamento":
        observacoes.append("Status: Em andamento")

    movimentacao = diario.movimentacao_material

    if movimentacao:
        descricao_material = (
            f"Material: {movimentacao.material} | "
            f"Movimentação: {movimentacao.numero_movimentacao} | "
            f"Recebimento: {movimentacao.status}"
        )

        if movimentacao.quantidade is not None:
            descricao_material += (
                f" | Quantidade: "
                f"{formatar_decimal_br(movimentacao.quantidade, 3)} "
                f"{movimentacao.unidade or ''}"
            )

        observacoes.append(descricao_material.strip())

    return [
        diario.data.strftime("%d/%m/%Y"),
        str(diario.km_inicial),
        str(diario.km_final) if diario.km_final is not None else "",
        "Sim" if houve_abastecimento else "Não",
        formatar_decimal_br(litros, 3) if houve_abastecimento else "",
        formatar_moeda_br(valor_total) if houve_abastecimento else "",
        diario.motorista.nome,
        " | ".join(observacoes),
    ]


def agrupar_diarios_pdf(diarios):
    grupos = {}

    for diario in sorted(
        diarios,
        key=lambda item: (
            (item.obra.nome if item.obra else ""),
            item.veiculo.placa,
            item.motorista.nome,
            item.data,
            item.hora_saida,
            item.id,
        ),
    ):
        chave = (
            diario.obra_id,
            diario.veiculo_id,
            diario.motorista_id,
        )
        grupos.setdefault(chave, []).append(diario)

    return list(grupos.values())


def desenhar_pagina_diario(pdf, diarios):
    largura_pagina, altura_pagina = A4
    margem_x = 18
    largura_util = largura_pagina - margem_x * 2
    topo = altura_pagina - 54

    diario_referencia = diarios[0] if diarios else None
    obra = (
        diario_referencia.obra.nome
        if diario_referencia and diario_referencia.obra
        else "SEM OBRA VINCULADA"
    )
    equipamento = (
        diario_referencia.veiculo.modelo
        if diario_referencia
        else "GERAL"
    )
    placa = (
        diario_referencia.veiculo.placa
        if diario_referencia
        else "GERAL"
    )
    motorista = (
        diario_referencia.motorista.nome
        if diario_referencia
        else "GERAL"
    )

    altura_timbre = 68
    pdf.setLineWidth(0.8)
    pdf.setStrokeColor(colors.black)
    pdf.rect(
        margem_x,
        topo - altura_timbre,
        largura_util,
        altura_timbre,
        stroke=1,
        fill=0,
    )

    altura_titulo = 27
    y_titulo = topo - altura_timbre - altura_titulo
    pdf.rect(
        margem_x,
        y_titulo,
        largura_util,
        altura_titulo,
        stroke=1,
        fill=0,
    )
    desenhar_texto_celula(
        pdf,
        "DIÁRIO DE EQUIPAMENTOS",
        margem_x,
        y_titulo,
        largura_util,
        altura_titulo,
        tamanho=16,
        negrito=True,
    )

    altura_campo = 15
    y_obra = y_titulo - altura_campo
    desenhar_campo_identificacao(
        pdf,
        "OBRA:",
        obra,
        margem_x,
        y_obra,
        largura_util,
        altura_campo,
        37,
    )

    y_equipamento = y_obra - altura_campo
    largura_equipamento = largura_util * 0.75
    desenhar_campo_identificacao(
        pdf,
        "EQUIPAMENTO:",
        equipamento,
        margem_x,
        y_equipamento,
        largura_equipamento,
        altura_campo,
        82,
    )
    desenhar_campo_identificacao(
        pdf,
        "PLACA:",
        placa,
        margem_x + largura_equipamento,
        y_equipamento,
        largura_util - largura_equipamento,
        altura_campo,
        40,
    )

    y_motorista = y_equipamento - altura_campo
    desenhar_campo_identificacao(
        pdf,
        "OPERADOR/MOTORISTA:",
        motorista,
        margem_x,
        y_motorista,
        largura_util,
        altura_campo,
        130,
    )

    larguras = [60, 56, 56, 50, 50, 68, 85]
    larguras.append(largura_util - sum(larguras))
    posicoes_x = [margem_x]

    for largura in larguras:
        posicoes_x.append(posicoes_x[-1] + largura)

    altura_cabecalho_1 = 20
    altura_cabecalho_2 = 18
    altura_linha = 16.5
    linhas_por_pagina = 31
    altura_tabela = (
        altura_cabecalho_1
        + altura_cabecalho_2
        + altura_linha * linhas_por_pagina
    )
    topo_tabela = y_motorista
    base_tabela = topo_tabela - altura_tabela
    y_meio_cabecalho = topo_tabela - altura_cabecalho_1
    y_dados = y_meio_cabecalho - altura_cabecalho_2

    pdf.setLineWidth(0.8)
    pdf.rect(
        margem_x,
        base_tabela,
        largura_util,
        altura_tabela,
        stroke=1,
        fill=0,
    )

    limites_principais = [1, 3, 6, 7]
    limites_secundarios = [2, 4, 5]

    for indice in limites_principais:
        x = posicoes_x[indice]
        pdf.line(x, base_tabela, x, topo_tabela)

    for indice in limites_secundarios:
        x = posicoes_x[indice]
        pdf.line(x, base_tabela, x, y_meio_cabecalho)

    pdf.line(
        posicoes_x[1],
        y_meio_cabecalho,
        posicoes_x[6],
        y_meio_cabecalho,
    )
    pdf.setLineWidth(1.1)
    pdf.line(margem_x, y_dados, margem_x + largura_util, y_dados)

    for indice in range(1, linhas_por_pagina + 1):
        y = y_dados - altura_linha * indice
        pdf.setLineWidth(0.55)
        pdf.line(margem_x, y, margem_x + largura_util, y)

    desenhar_texto_celula(
        pdf,
        "DATA",
        posicoes_x[0],
        y_dados,
        larguras[0],
        altura_cabecalho_1 + altura_cabecalho_2,
        tamanho=8,
        negrito=True,
    )
    desenhar_texto_celula(
        pdf,
        "KM/HOR",
        posicoes_x[1],
        y_meio_cabecalho,
        larguras[1] + larguras[2],
        altura_cabecalho_1,
        tamanho=8,
        negrito=True,
    )
    desenhar_texto_celula(
        pdf,
        "ABASTECIMENTO",
        posicoes_x[3],
        y_meio_cabecalho,
        larguras[3] + larguras[4] + larguras[5],
        altura_cabecalho_1,
        tamanho=8,
        negrito=True,
    )
    desenhar_texto_celula(
        pdf,
        "ASSINATURA",
        posicoes_x[6],
        y_dados,
        larguras[6],
        altura_cabecalho_1 + altura_cabecalho_2,
        tamanho=8,
        negrito=True,
    )
    desenhar_texto_celula(
        pdf,
        "OBSERVAÇÃO",
        posicoes_x[7],
        y_dados,
        larguras[7],
        altura_cabecalho_1 + altura_cabecalho_2,
        tamanho=7.5,
        negrito=True,
    )

    subtitulos = ["INICIAL", "FINAL", "HOUVE?", "LITROS", "VALOR TOTAL"]

    for deslocamento, texto in enumerate(subtitulos, start=1):
        desenhar_texto_celula(
            pdf,
            texto,
            posicoes_x[deslocamento],
            y_dados,
            larguras[deslocamento],
            altura_cabecalho_2,
            tamanho=7,
            negrito=True,
        )

    for indice_linha in range(linhas_por_pagina):
        if indice_linha >= len(diarios):
            continue

        valores = dados_linha_diario(diarios[indice_linha])
        y = y_dados - altura_linha * (indice_linha + 1)

        for indice_coluna, valor in enumerate(valores):
            tamanho = 6.2
            alinhamento = "center"

            if indice_coluna == 6:
                tamanho = 5.2

            if indice_coluna == 7:
                tamanho = 5.2
                alinhamento = "left"

            desenhar_texto_celula(
                pdf,
                valor,
                posicoes_x[indice_coluna],
                y,
                larguras[indice_coluna],
                altura_linha,
                tamanho=tamanho,
                alinhamento=alinhamento,
            )

    pdf.showPage()


def gerar_pdf_diarios(diarios):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle("Diário de Equipamentos")
    pdf.setAuthor(
        current_user.empresa.nome_fantasia
        or current_user.empresa.razao_social
    )
    grupos = agrupar_diarios_pdf(diarios)

    if not grupos:
        desenhar_pagina_diario(pdf, [])
    else:
        linhas_por_pagina = 31

        for grupo in grupos:
            for inicio in range(0, len(grupo), linhas_por_pagina):
                desenhar_pagina_diario(
                    pdf,
                    grupo[inicio:inicio + linhas_por_pagina],
                )

    pdf.save()
    buffer.seek(0)
    return buffer


@diario_bp.route("/diario")
@login_required
def listar_diarios():
    empresa = current_user.empresa

    veiculos = Veiculo.query.filter_by(empresa_id=empresa.id).order_by(
        Veiculo.placa.asc()
    ).all()

    motoristas = Motorista.query.filter_by(empresa_id=empresa.id).order_by(
        Motorista.nome.asc()
    ).all()

    obras = Obra.query.filter_by(empresa_id=empresa.id).order_by(
        Obra.nome.asc()
    ).all()

    filtros = obter_filtros_diario()
    consulta = aplicar_filtros_diario(
        DiarioBordo.query.filter_by(empresa_id=empresa.id),
        filtros,
    )

    diarios = consulta.order_by(
        DiarioBordo.data.desc(),
        DiarioBordo.hora_saida.desc(),
        DiarioBordo.id.desc(),
    ).all()

    todos_diarios = DiarioBordo.query.filter_by(empresa_id=empresa.id).all()
    diarios_abertos = [
        diario for diario in todos_diarios if diario.status == "Em andamento"
    ]

    return render_template(
        "diario.html",
        diarios=diarios,
        diarios_abertos=diarios_abertos,
        veiculos=veiculos,
        motoristas=motoristas,
        obras=obras,
        hoje=date.today().isoformat(),
        hora_atual=datetime.now().strftime("%H:%M"),
        total_diarios=len(todos_diarios),
        total_em_andamento=len(diarios_abertos),
        total_concluidos=sum(
            1 for diario in todos_diarios if diario.status == "Concluído"
        ),
        total_km=sum(diario.km_percorrida or 0 for diario in todos_diarios),
        motoristas_com_diario_aberto={
            diario.motorista_id for diario in diarios_abertos
        },
        veiculos_com_diario_aberto={
            diario.veiculo_id for diario in diarios_abertos
        },
        status_filtro=filtros["status"],
        veiculo_filtro=filtros["veiculo_id"],
        motorista_filtro=filtros["motorista_id"],
        data_inicio_filtro=filtros["data_inicio_texto"],
        data_fim_filtro=filtros["data_fim_texto"],
    )


@diario_bp.route("/movimentacoes-materiais")
@login_required
def listar_movimentacoes_materiais():
    empresa = current_user.empresa
    status = request.args.get("status", "").strip()
    placa = request.args.get("placa", "").strip().upper()
    material = request.args.get("material", "").strip()
    numero = request.args.get("numero_movimentacao", "").strip()
    data_inicio_texto = request.args.get("data_inicio", "")
    data_fim_texto = request.args.get("data_fim", "")
    data_inicio = converter_data(data_inicio_texto)
    data_fim = converter_data(data_fim_texto)

    if status not in STATUS_MOVIMENTACAO:
        status = ""

    consulta = (
        MovimentacaoMaterial.query
        .filter_by(empresa_id=empresa.id)
        .join(MovimentacaoMaterial.diario_bordo)
        .join(DiarioBordo.veiculo)
        .options(
            joinedload(MovimentacaoMaterial.diario_bordo)
            .joinedload(DiarioBordo.veiculo),
            joinedload(MovimentacaoMaterial.diario_bordo)
            .joinedload(DiarioBordo.motorista),
            joinedload(MovimentacaoMaterial.diario_bordo)
            .joinedload(DiarioBordo.obra),
            joinedload(MovimentacaoMaterial.recebido_por),
            joinedload(MovimentacaoMaterial.cancelado_por),
        )
    )

    if status:
        consulta = consulta.filter(MovimentacaoMaterial.status == status)

    if placa:
        consulta = consulta.filter(Veiculo.placa.ilike(f"%{placa}%"))

    if material:
        consulta = consulta.filter(
            MovimentacaoMaterial.material.ilike(f"%{material}%")
        )

    if numero:
        consulta = consulta.filter(
            MovimentacaoMaterial.numero_movimentacao.ilike(f"%{numero}%")
        )

    if data_inicio:
        consulta = consulta.filter(DiarioBordo.data >= data_inicio)

    if data_fim:
        consulta = consulta.filter(DiarioBordo.data <= data_fim)

    movimentacoes = consulta.order_by(
        DiarioBordo.data.desc(),
        DiarioBordo.hora_saida.desc(),
        MovimentacaoMaterial.id.desc(),
    ).all()

    todas = MovimentacaoMaterial.query.filter_by(
        empresa_id=empresa.id,
    ).all()
    hoje = date.today()

    return render_template(
        "movimentacoes_materiais.html",
        movimentacoes=movimentacoes,
        total_movimentacoes=len(todas),
        total_em_transito=sum(
            1 for item in todas if item.status == "Em trânsito"
        ),
        total_recebidas_hoje=sum(
            1
            for item in todas
            if item.recebido_em is not None
            and item.recebido_em.date() == hoje
        ),
        total_ressalvas=sum(
            1 for item in todas if item.status == "Recebido com ressalva"
        ),
        status_filtro=status,
        placa_filtro=placa,
        material_filtro=material,
        numero_filtro=numero,
        data_inicio_filtro=data_inicio_texto,
        data_fim_filtro=data_fim_texto,
    )


@diario_bp.route(
    "/movimentacoes-materiais/<int:movimentacao_id>/cancelar",
    methods=["POST"],
)
@login_required
def cancelar_movimentacao_material(movimentacao_id):
    perfis_permitidos = {"administrador", "gestor", "frota"}

    if (current_user.perfil or "").strip().lower() not in perfis_permitidos:
        abort(403)

    movimentacao = MovimentacaoMaterial.query.filter_by(
        id=movimentacao_id,
        empresa_id=current_user.empresa_id,
    ).first()

    if movimentacao is None:
        abort(404)

    if movimentacao.status != "Em trânsito":
        flash(
            "Somente movimentações em trânsito podem ser canceladas.",
            "warning",
        )
        return redirect(url_for("diario.listar_movimentacoes_materiais"))

    motivo = request.form.get("motivo", "").strip()

    if not motivo:
        flash("Informe o motivo do cancelamento.", "warning")
        return redirect(url_for("diario.listar_movimentacoes_materiais"))

    movimentacao.status = "Cancelado"
    movimentacao.cancelado_em = agora_local()
    movimentacao.cancelado_por_id = current_user.id
    movimentacao.motivo_cancelamento = motivo
    db.session.commit()

    flash("Movimentação cancelada com sucesso.", "success")
    return redirect(url_for("diario.listar_movimentacoes_materiais"))


@diario_bp.route("/diario/exportar-pdf")
@login_required
def exportar_pdf():
    empresa = current_user.empresa
    filtros = obter_filtros_diario()
    consulta = DiarioBordo.query.filter_by(
        empresa_id=empresa.id,
    ).options(
        joinedload(DiarioBordo.veiculo),
        joinedload(DiarioBordo.motorista),
        joinedload(DiarioBordo.obra),
        selectinload(DiarioBordo.abastecimentos),
        joinedload(DiarioBordo.movimentacao_material),
    )
    consulta = aplicar_filtros_diario(consulta, filtros)
    diarios = consulta.order_by(
        DiarioBordo.data.asc(),
        DiarioBordo.hora_saida.asc(),
        DiarioBordo.id.asc(),
    ).all()
    arquivo = gerar_pdf_diarios(diarios)
    nome_arquivo = (
        "diario-de-bordo-"
        f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf"
    )

    return send_file(
        arquivo,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=nome_arquivo,
    )


@diario_bp.route("/diario/novo", methods=["POST"])
@login_required
def novo_diario():
    empresa = current_user.empresa
    dados = obter_dados_formulario(
        empresa.id,
        usar_veiculo_vinculado=True,
    )

    erro = validar_dados(
        dados,
        empresa.id,
        exigir_veiculo_vinculado=True,
    )

    if erro:
        flash(erro, "warning")
        return redirect(url_for("diario.listar_diarios"))

    dados_abastecimento = obter_dados_abastecimento(dados["veiculo"])
    erro_abastecimento = validar_abastecimento(dados_abastecimento)

    if erro_abastecimento:
        flash(erro_abastecimento, "warning")
        return redirect(url_for("diario.listar_diarios"))

    dados_material = obter_dados_material()
    erro_material = validar_material(dados_material)

    if erro_material:
        flash(erro_material, "warning")
        return redirect(url_for("diario.listar_diarios"))

    diario = DiarioBordo(
        empresa_id=empresa.id,
        veiculo_id=dados["veiculo"].id,
        motorista_id=dados["motorista"].id,
        obra_id=dados["obra"].id if dados["obra"] else None,
        data=dados["data"],
        hora_saida=dados["hora_saida"],
        hora_retorno=None,
        km_inicial=dados["km_inicial"],
        km_final=None,
        origem=dados["origem"],
        destino=dados["destino"],
        finalidade=dados["finalidade"] or None,
        ocorrencias=dados["ocorrencias"] or None,
        status="Em andamento",
    )

    arquivos_salvos = []

    try:
        db.session.add(diario)
        db.session.flush()

        if dados_material["transporta"]:
            movimentacao = MovimentacaoMaterial(
                empresa_id=empresa.id,
                diario_bordo_id=diario.id,
                material=dados_material["material"],
                numero_movimentacao=dados_material["numero_movimentacao"],
                quantidade=dados_material["quantidade"],
                unidade=dados_material["unidade"] or None,
                observacao_carga=dados_material["observacao"] or None,
                status="Em trânsito",
            )
            db.session.add(movimentacao)

        if dados_abastecimento["houve"]:
            foto_odometro = salvar_arquivo_abastecimento(
                dados_abastecimento["foto_odometro"],
                empresa.id,
                "odometro",
                EXTENSOES_IMAGEM,
            )
            arquivos_salvos.append(foto_odometro)

            cupom_fiscal = salvar_arquivo_abastecimento(
                dados_abastecimento["cupom_fiscal"],
                empresa.id,
                "placa",
                EXTENSOES_IMAGEM,
            )
            arquivos_salvos.append(cupom_fiscal)

            abastecimento = Abastecimento(
                empresa_id=empresa.id,
                usuario_id=current_user.id,
                veiculo_id=dados["veiculo"].id,
                motorista_id=dados["motorista"].id,
                obra_id=dados["obra"].id if dados["obra"] else None,
                diario_bordo_id=diario.id,
                data=dados["data"],
                hora=dados["hora_saida"],
                posto=dados_abastecimento["posto"],
                combustivel=dados_abastecimento["combustivel"],
                litros=dados_abastecimento["litros"],
                valor_litro=dados_abastecimento["valor_litro"],
                valor_total=calcular_valor_total(
                    dados_abastecimento["litros"],
                    dados_abastecimento["valor_litro"],
                ),
                km=dados["km_inicial"],
                tanque_cheio=dados_abastecimento["tanque_cheio"],
                numero_nota=dados_abastecimento["numero_nota"] or None,
                comprovante=cupom_fiscal,
                foto_odometro=foto_odometro,
                observacoes=(
                    f"Registrado na abertura do diário de bordo #{diario.id}."
                ),
            )
            db.session.add(abastecimento)

        if dados["km_inicial"] > dados["veiculo"].km_atual:
            dados["veiculo"].km_atual = dados["km_inicial"]

        db.session.commit()
    except ValueError as erro_arquivo:
        db.session.rollback()

        for caminho in arquivos_salvos:
            remover_arquivo(caminho)

        flash(str(erro_arquivo), "warning")
        return redirect(url_for("diario.listar_diarios"))
    except Exception:
        db.session.rollback()

        for caminho in arquivos_salvos:
            remover_arquivo(caminho)

        current_app.logger.exception("Falha ao criar diário de bordo")
        flash(
            "Não foi possível iniciar o diário. Nenhum registro foi gravado.",
            "danger",
        )
        return redirect(url_for("diario.listar_diarios"))

    mensagem = "Diário iniciado e mantido em andamento."

    if dados_abastecimento["houve"]:
        mensagem += " O abastecimento também foi registrado."

    if dados_material["transporta"]:
        mensagem += " A movimentação de material está em trânsito."

    flash(mensagem, "success")
    return redirect(url_for("diario.listar_diarios"))


@diario_bp.route("/diario/<int:diario_id>/finalizar", methods=["POST"])
@login_required
def finalizar_diario(diario_id):
    empresa = current_user.empresa
    diario = DiarioBordo.query.filter_by(
        id=diario_id,
        empresa_id=empresa.id,
    ).first()

    if diario is None:
        abort(404)

    if diario.status != "Em andamento":
        flash("Esse diário já foi finalizado.", "warning")
        return redirect(url_for("diario.listar_diarios"))

    movimentacao = diario.movimentacao_material

    if movimentacao and movimentacao.status == "Em trânsito":
        flash(
            "Esta viagem será concluída automaticamente quando o apontador "
            "confirmar o recebimento do material.",
            "warning",
        )
        return redirect(url_for("diario.listar_diarios"))

    if movimentacao and movimentacao.recebida:
        diario.hora_retorno = (
            movimentacao.recebido_em.time().replace(microsecond=0)
            if movimentacao.recebido_em
            else agora_local().time().replace(microsecond=0)
        )
        diario.status = "Concluído"
        db.session.commit()
        flash(
            "Viagem concluída pelo recebimento confirmado pelo apontador.",
            "success",
        )
        return redirect(url_for("diario.listar_diarios"))

    hora_chegada = converter_hora(request.form.get("hora_chegada"))
    km_final = converter_inteiro(request.form.get("km_final"))

    if hora_chegada is None:
        flash("Informe uma hora de chegada válida.", "warning")
        return redirect(url_for("diario.listar_diarios"))

    if km_final is None or km_final < diario.km_inicial:
        flash(
            "O KM final deve ser igual ou maior que o KM inicial.",
            "warning",
        )
        return redirect(url_for("diario.listar_diarios"))

    try:
        diario.hora_retorno = hora_chegada
        diario.km_final = km_final
        diario.status = "Concluído"

        if km_final > diario.veiculo.km_atual:
            diario.veiculo.km_atual = km_final

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao finalizar diário de bordo")
        flash("Não foi possível finalizar o diário.", "danger")
        return redirect(url_for("diario.listar_diarios"))

    flash("Diário finalizado com sucesso.", "success")
    return redirect(url_for("diario.listar_diarios"))


@diario_bp.route("/diario/<int:diario_id>/editar", methods=["POST"])
@login_required
def editar_diario(diario_id):
    empresa = current_user.empresa
    diario = DiarioBordo.query.filter_by(
        id=diario_id,
        empresa_id=empresa.id,
    ).first()

    if diario is None:
        abort(404)

    dados = obter_dados_formulario(empresa.id)
    erro = validar_dados(
        dados,
        empresa.id,
        diario_id=diario.id,
        verificar_diario_aberto=(diario.status == "Em andamento"),
    )

    if (
        not erro
        and diario.km_final is not None
        and diario.km_final < dados["km_inicial"]
    ):
        erro = "O KM inicial não pode ser maior que o KM final já registrado."

    if erro:
        flash(erro, "warning")
        return redirect(url_for("diario.listar_diarios"))

    diario.veiculo_id = dados["veiculo"].id
    diario.motorista_id = dados["motorista"].id
    diario.obra_id = dados["obra"].id if dados["obra"] else None
    diario.data = dados["data"]
    diario.hora_saida = dados["hora_saida"]
    diario.km_inicial = dados["km_inicial"]
    diario.origem = dados["origem"]
    diario.destino = dados["destino"]
    diario.finalidade = dados["finalidade"] or None
    diario.ocorrencias = dados["ocorrencias"] or None

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao editar diário de bordo")
        flash("Não foi possível atualizar o diário.", "danger")
        return redirect(url_for("diario.listar_diarios"))

    flash("Diário de bordo atualizado com sucesso.", "success")
    return redirect(url_for("diario.listar_diarios"))
