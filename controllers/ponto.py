import math
import os
import uuid
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont, ImageOps

from database.models import (
    Colaborador,
    LocalTrabalho,
    Motorista,
    PontoMarcacao,
    Usuario,
)
from extensions import db


ponto_bp = Blueprint("ponto", __name__)

TIPOS_PONTO = {
    "entrada": "Entrada",
    "intervalo": "Início do intervalo",
    "retorno": "Retorno do intervalo",
    "saida": "Saída",
}

SEQUENCIA_PONTO = (
    "entrada",
    "intervalo",
    "retorno",
    "saida",
)

EXTENSOES_IMAGEM = {"jpg", "jpeg", "png", "webp", "heic"}


def eh_administrador():
    return (current_user.perfil or "").strip().lower() == "administrador"


def parse_float(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def parse_datetime(valor):
    if not valor:
        return datetime.utcnow()

    texto = str(valor).strip().replace("Z", "+00:00")
    try:
        data = datetime.fromisoformat(texto)
        if data.tzinfo is not None:
            data = data.astimezone().replace(tzinfo=None)
        return data
    except ValueError:
        return datetime.utcnow()


def distancia_metros(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None

    raio_terra = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(delta_lambda / 2) ** 2
    )
    return raio_terra * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def colaborador_do_usuario():
    return Colaborador.query.filter_by(
        empresa_id=current_user.empresa_id,
        usuario_id=current_user.id,
        ativo=True,
    ).first()


def obter_proximo_tipo_ponto(
    colaborador_id,
    data_referencia,
):
    inicio = data_referencia.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    fim = inicio + timedelta(days=1)

    quantidade_marcacoes = (
        PontoMarcacao.query
        .filter(
            PontoMarcacao.empresa_id
            == current_user.empresa_id,
            PontoMarcacao.colaborador_id
            == colaborador_id,
            PontoMarcacao.capturado_em
            >= inicio,
            PontoMarcacao.capturado_em
            < fim,
        )
        .count()
    )

    if quantidade_marcacoes >= len(
        SEQUENCIA_PONTO
    ):
        return None

    return SEQUENCIA_PONTO[
        quantidade_marcacoes
    ]


def carregar_fonte(tamanho):
    fontes = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]

    for caminho in fontes:
        if caminho.exists():
            try:
                return ImageFont.truetype(str(caminho), tamanho)
            except OSError:
                pass

    return ImageFont.load_default()


def formatar_distancia(distancia):
    if distancia is None:
        return "Não calculada"

    if distancia >= 1000:
        return f"{distancia / 1000:.2f} km"

    return f"{distancia:.0f} m"


def salvar_foto(
    arquivo,
    empresa_id,
    colaborador,
    client_uuid,
    capturado_em,
    latitude,
    longitude,
    precisao,
    dentro_geocerca,
    distancia,
):
    if arquivo is None or not arquivo.filename:
        raise ValueError("A foto facial é obrigatória.")

    extensao = (
        arquivo.filename.rsplit(".", 1)[-1].lower()
        if "." in arquivo.filename
        else ""
    )
    if extensao not in EXTENSOES_IMAGEM:
        raise ValueError("Envie uma imagem JPG, PNG, WEBP ou HEIC.")

    pasta_relativa = (
        Path("uploads")
        / "ponto"
        / str(empresa_id)
        / str(colaborador.id)
    )
    pasta_absoluta = Path(current_app.static_folder) / pasta_relativa
    pasta_originais = pasta_absoluta / "originais"

    pasta_absoluta.mkdir(parents=True, exist_ok=True)
    pasta_originais.mkdir(parents=True, exist_ok=True)

    nome_original_seguro = secure_filename(arquivo.filename)
    nome_original = (
        f"{client_uuid}_{nome_original_seguro}"
        if nome_original_seguro
        else f"{client_uuid}_foto.{extensao}"
    )
    caminho_original = pasta_originais / nome_original
    arquivo.save(caminho_original)

    nome_marcado = f"{client_uuid}_identificada.jpg"
    caminho_marcado = pasta_absoluta / nome_marcado

    try:
        with Image.open(caminho_original) as imagem_aberta:
            imagem = ImageOps.exif_transpose(imagem_aberta).convert("RGB")

        largura, altura = imagem.size
        tamanho_fonte = max(18, min(42, largura // 32))
        fonte = carregar_fonte(tamanho_fonte)
        fonte_pequena = carregar_fonte(max(15, int(tamanho_fonte * 0.82)))

        if dentro_geocerca is True:
            situacao = "Dentro da área"
        elif dentro_geocerca is False:
            situacao = f"Fora da área — {formatar_distancia(distancia)}"
        else:
            situacao = "Localização não validada"

        coordenadas = (
            f"{latitude:.6f}, {longitude:.6f}"
            if latitude is not None and longitude is not None
            else "Não informadas"
        )
        precisao_texto = (
            f"{precisao:.0f} m"
            if precisao is not None
            else "Não informada"
        )

        linhas = [
            f"Colaborador: {colaborador.nome}",
            f"Data/hora: {capturado_em.strftime('%d/%m/%Y %H:%M:%S')}",
            f"Coordenadas: {coordenadas}",
            f"Precisão GPS: {precisao_texto}",
            f"Situação: {situacao}",
        ]

        margem = max(18, largura // 45)
        espacamento = max(8, tamanho_fonte // 3)

        camada = Image.new("RGBA", imagem.size, (0, 0, 0, 0))
        desenho = ImageDraw.Draw(camada)

        alturas = []
        for indice, linha in enumerate(linhas):
            fonte_linha = fonte if indice < 2 else fonte_pequena
            caixa = desenho.textbbox((0, 0), linha, font=fonte_linha)
            alturas.append(caixa[3] - caixa[1])

        altura_faixa = (
            margem * 2
            + sum(alturas)
            + espacamento * (len(linhas) - 1)
        )
        topo = max(0, altura - altura_faixa)

        desenho.rectangle(
            [(0, topo), (largura, altura)],
            fill=(0, 0, 0, 185),
        )

        y = topo + margem
        for indice, linha in enumerate(linhas):
            fonte_linha = fonte if indice < 2 else fonte_pequena
            desenho.text(
                (margem, y),
                linha,
                font=fonte_linha,
                fill=(255, 255, 255, 255),
                stroke_width=1,
                stroke_fill=(0, 0, 0, 255),
            )
            y += alturas[indice] + espacamento

        imagem_final = Image.alpha_composite(
            imagem.convert("RGBA"),
            camada,
        ).convert("RGB")
        imagem_final.save(caminho_marcado, "JPEG", quality=92, optimize=True)

        return (pasta_relativa / nome_marcado).as_posix()

    except Exception:
        current_app.logger.exception(
            "Não foi possível inserir dados na foto. A imagem original será usada."
        )
        return (
            pasta_relativa / "originais" / nome_original
        ).as_posix()


def validar_usuario_colaborador(usuario_id, colaborador_id=None):
    """
    Retorna o colaborador já vinculado ao usuário, se existir.
    Na edição, ignora o próprio colaborador.
    """
    if not usuario_id:
        return None

    consulta = Colaborador.query.filter(
        Colaborador.empresa_id == current_user.empresa_id,
        Colaborador.usuario_id == int(usuario_id),
    )

    if colaborador_id is not None:
        consulta = consulta.filter(Colaborador.id != int(colaborador_id))

    return consulta.first()


def obter_motorista_empresa(motorista_id):
    if not motorista_id:
        return None

    try:
        identificador = int(motorista_id)
    except (TypeError, ValueError):
        return None

    return Motorista.query.filter_by(
        id=identificador,
        empresa_id=current_user.empresa_id,
    ).first()


def validar_motorista_colaborador(motorista_id, colaborador_id=None):
    """Retorna outro colaborador que já usa o motorista selecionado."""
    if not motorista_id:
        return None

    consulta = Colaborador.query.filter(
        Colaborador.empresa_id == current_user.empresa_id,
        Colaborador.motorista_id == int(motorista_id),
    )

    if colaborador_id is not None:
        consulta = consulta.filter(Colaborador.id != int(colaborador_id))

    return consulta.first()


@ponto_bp.route("/cadastros/colaboradores", methods=["GET", "POST"])
@login_required
def colaboradores():
    if not eh_administrador():
        flash("Acesso permitido somente para administradores.", "warning")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        matricula = request.form.get("matricula", "").strip()
        funcao = request.form.get("funcao", "").strip() or None
        telefone = request.form.get("telefone", "").strip() or None
        usuario_id = request.form.get("usuario_id") or None
        motorista_id = request.form.get("motorista_id") or None
        local_id = request.form.get("local_trabalho_id") or None
        jornada_horas = parse_float(request.form.get("jornada_horas")) or 8

        if not nome or not matricula:
            flash("Informe nome e matrícula.", "warning")
            return redirect(url_for("ponto.colaboradores"))

        existente = Colaborador.query.filter_by(
            empresa_id=current_user.empresa_id,
            matricula=matricula,
        ).first()
        if existente:
            flash("Já existe colaborador com essa matrícula.", "warning")
            return redirect(url_for("ponto.colaboradores"))

        usuario_vinculado = validar_usuario_colaborador(usuario_id)
        if usuario_vinculado:
            flash(
                f"O usuário selecionado já está vinculado ao colaborador "
                f"{usuario_vinculado.nome}. Edite esse colaborador ou escolha outro usuário.",
                "danger",
            )
            return redirect(url_for("ponto.colaboradores"))

        motorista = obter_motorista_empresa(motorista_id)
        if motorista_id and motorista is None:
            flash("O motorista selecionado não é válido para esta empresa.", "danger")
            return redirect(url_for("ponto.colaboradores"))

        motorista_vinculado = validar_motorista_colaborador(motorista_id)
        if motorista_vinculado:
            flash(
                f"O motorista selecionado já está vinculado ao colaborador "
                f"{motorista_vinculado.nome}.",
                "danger",
            )
            return redirect(url_for("ponto.colaboradores"))

        try:
            colaborador = Colaborador(
                empresa_id=current_user.empresa_id,
                nome=nome,
                matricula=matricula,
                funcao=funcao,
                telefone=telefone,
                usuario_id=int(usuario_id) if usuario_id else None,
                motorista_id=motorista.id if motorista else None,
                local_trabalho_id=int(local_id) if local_id else None,
                jornada_diaria_minutos=int(jornada_horas * 60),
                ativo=True,
            )
            db.session.add(colaborador)
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao cadastrar colaborador")
            flash("Não foi possível cadastrar o colaborador. Verifique os dados.", "danger")
            return redirect(url_for("ponto.colaboradores"))

        flash("Colaborador cadastrado com sucesso.", "success")
        return redirect(url_for("ponto.colaboradores"))

    itens = Colaborador.query.filter_by(
        empresa_id=current_user.empresa_id
    ).order_by(Colaborador.nome.asc()).all()

    usuarios = Usuario.query.filter_by(
        empresa_id=current_user.empresa_id,
        ativo=True,
    ).order_by(Usuario.nome.asc()).all()

    locais = LocalTrabalho.query.filter_by(
        empresa_id=current_user.empresa_id,
        ativo=True,
    ).order_by(LocalTrabalho.nome.asc()).all()

    motoristas = Motorista.query.filter_by(
        empresa_id=current_user.empresa_id,
    ).order_by(Motorista.nome.asc()).all()

    return render_template(
        "cadastros/colaboradores.html",
        colaboradores=itens,
        usuarios=usuarios,
        locais=locais,
        motoristas=motoristas,
    )


@ponto_bp.route("/cadastros/colaboradores/<int:colaborador_id>/editar", methods=["POST"])
@login_required
def editar_colaborador(colaborador_id):
    if not eh_administrador():
        flash("Acesso permitido somente para administradores.", "warning")
        return redirect(url_for("dashboard"))

    colaborador = Colaborador.query.filter_by(
        id=colaborador_id,
        empresa_id=current_user.empresa_id,
    ).first_or_404()

    nome = request.form.get("nome", "").strip()
    matricula = request.form.get("matricula", "").strip()
    funcao = request.form.get("funcao", "").strip() or None
    telefone = request.form.get("telefone", "").strip() or None
    usuario_id = request.form.get("usuario_id") or None
    motorista_id = request.form.get("motorista_id") or None
    local_id = request.form.get("local_trabalho_id") or None
    jornada_horas = parse_float(request.form.get("jornada_horas")) or 8

    if not nome or not matricula:
        flash("Informe nome e matrícula.", "warning")
        return redirect(url_for("ponto.colaboradores"))

    matricula_existente = Colaborador.query.filter(
        Colaborador.empresa_id == current_user.empresa_id,
        Colaborador.matricula == matricula,
        Colaborador.id != colaborador.id,
    ).first()

    if matricula_existente:
        flash("Já existe outro colaborador com essa matrícula.", "warning")
        return redirect(url_for("ponto.colaboradores"))

    usuario_vinculado = validar_usuario_colaborador(
        usuario_id,
        colaborador_id=colaborador.id,
    )
    if usuario_vinculado:
        flash(
            f"O usuário selecionado já está vinculado ao colaborador "
            f"{usuario_vinculado.nome}.",
            "danger",
        )
        return redirect(url_for("ponto.colaboradores"))

    motorista = obter_motorista_empresa(motorista_id)
    if motorista_id and motorista is None:
        flash("O motorista selecionado não é válido para esta empresa.", "danger")
        return redirect(url_for("ponto.colaboradores"))

    motorista_vinculado = validar_motorista_colaborador(
        motorista_id,
        colaborador_id=colaborador.id,
    )
    if motorista_vinculado:
        flash(
            f"O motorista selecionado já está vinculado ao colaborador "
            f"{motorista_vinculado.nome}.",
            "danger",
        )
        return redirect(url_for("ponto.colaboradores"))

    try:
        colaborador.nome = nome
        colaborador.matricula = matricula
        colaborador.funcao = funcao
        colaborador.telefone = telefone
        colaborador.usuario_id = int(usuario_id) if usuario_id else None
        colaborador.motorista_id = motorista.id if motorista else None
        colaborador.local_trabalho_id = int(local_id) if local_id else None
        colaborador.jornada_diaria_minutos = int(jornada_horas * 60)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erro ao editar colaborador")
        flash("Não foi possível atualizar o colaborador.", "danger")
        return redirect(url_for("ponto.colaboradores"))

    flash("Colaborador atualizado com sucesso.", "success")
    return redirect(url_for("ponto.colaboradores"))


@ponto_bp.route("/cadastros/colaboradores/<int:colaborador_id>/alternar-status", methods=["POST"])
@login_required
def alternar_status_colaborador(colaborador_id):
    if not eh_administrador():
        flash("Acesso permitido somente para administradores.", "warning")
        return redirect(url_for("dashboard"))

    colaborador = Colaborador.query.filter_by(
        id=colaborador_id,
        empresa_id=current_user.empresa_id,
    ).first_or_404()

    try:
        colaborador.ativo = not colaborador.ativo
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erro ao alterar status do colaborador")
        flash("Não foi possível alterar o status do colaborador.", "danger")
        return redirect(url_for("ponto.colaboradores"))

    estado = "ativado" if colaborador.ativo else "desativado"
    flash(f"Colaborador {estado} com sucesso.", "success")
    return redirect(url_for("ponto.colaboradores"))


@ponto_bp.route("/cadastros/locais-trabalho", methods=["GET", "POST"])
@login_required
def locais_trabalho():
    if not eh_administrador():
        flash("Acesso permitido somente para administradores.", "warning")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        if not nome:
            flash("Informe o nome do local.", "warning")
            return redirect(url_for("ponto.locais_trabalho"))

        local = LocalTrabalho(
            empresa_id=current_user.empresa_id,
            nome=nome,
            endereco=request.form.get("endereco", "").strip() or None,
            latitude=parse_float(request.form.get("latitude")),
            longitude=parse_float(request.form.get("longitude")),
            raio_metros=int(parse_float(request.form.get("raio_metros")) or 200),
            ativo=True,
        )
        db.session.add(local)
        db.session.commit()
        flash("Local de trabalho cadastrado.", "success")
        return redirect(url_for("ponto.locais_trabalho"))

    locais = LocalTrabalho.query.filter_by(
        empresa_id=current_user.empresa_id
    ).order_by(LocalTrabalho.nome.asc()).all()
    return render_template("cadastros/locais_trabalho.html", locais=locais)



@ponto_bp.route(
    "/cadastros/locais-trabalho/<int:local_id>/editar",
    methods=["POST"],
)
@login_required
def editar_local_trabalho(local_id):
    if not eh_administrador():
        flash(
            "Acesso permitido somente para administradores.",
            "warning",
        )
        return redirect(url_for("dashboard"))

    local = LocalTrabalho.query.filter_by(
        id=local_id,
        empresa_id=current_user.empresa_id,
    ).first_or_404()

    nome = request.form.get("nome", "").strip()
    endereco = (
        request.form.get("endereco", "").strip()
        or None
    )

    latitude = parse_float(
        request.form.get("latitude")
    )

    longitude = parse_float(
        request.form.get("longitude")
    )

    raio_metros = int(
        parse_float(
            request.form.get("raio_metros")
        )
        or 200
    )

    if not nome:
        flash(
            "Informe o nome do local.",
            "warning",
        )
        return redirect(
            url_for("ponto.locais_trabalho")
        )

    if latitude is not None and not -90 <= latitude <= 90:
        flash(
            "A latitude deve estar entre -90 e 90.",
            "warning",
        )
        return redirect(
            url_for("ponto.locais_trabalho")
        )

    if longitude is not None and not -180 <= longitude <= 180:
        flash(
            "A longitude deve estar entre -180 e 180.",
            "warning",
        )
        return redirect(
            url_for("ponto.locais_trabalho")
        )

    if raio_metros < 10:
        flash(
            "O raio permitido deve ser de pelo menos 10 metros.",
            "warning",
        )
        return redirect(
            url_for("ponto.locais_trabalho")
        )

    local_existente = LocalTrabalho.query.filter(
        LocalTrabalho.empresa_id
        == current_user.empresa_id,
        LocalTrabalho.nome == nome,
        LocalTrabalho.id != local.id,
    ).first()

    if local_existente:
        flash(
            "Já existe outro local com esse nome.",
            "warning",
        )
        return redirect(
            url_for("ponto.locais_trabalho")
        )

    try:
        local.nome = nome
        local.endereco = endereco
        local.latitude = latitude
        local.longitude = longitude
        local.raio_metros = raio_metros

        db.session.commit()

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Erro ao editar local de trabalho"
        )

        flash(
            "Não foi possível atualizar o local de trabalho.",
            "danger",
        )

        return redirect(
            url_for("ponto.locais_trabalho")
        )

    flash(
        "Local de trabalho atualizado com sucesso.",
        "success",
    )

    return redirect(
        url_for("ponto.locais_trabalho")
    )


@ponto_bp.route(
    "/cadastros/locais-trabalho/<int:local_id>/alternar-status",
    methods=["POST"],
)
@login_required
def alternar_status_local_trabalho(local_id):
    if not eh_administrador():
        flash(
            "Acesso permitido somente para administradores.",
            "warning",
        )
        return redirect(url_for("dashboard"))

    local = LocalTrabalho.query.filter_by(
        id=local_id,
        empresa_id=current_user.empresa_id,
    ).first_or_404()

    try:
        local.ativo = not local.ativo
        db.session.commit()

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Erro ao alterar status do local de trabalho"
        )

        flash(
            "Não foi possível alterar o status do local.",
            "danger",
        )

        return redirect(
            url_for("ponto.locais_trabalho")
        )

    estado = (
        "ativado"
        if local.ativo
        else "desativado"
    )

    flash(
        f"Local de trabalho {estado} com sucesso.",
        "success",
    )

    return redirect(
        url_for("ponto.locais_trabalho")
    )


@ponto_bp.route("/ponto-eletronico")
@login_required
def coleta():
    colaborador = colaborador_do_usuario()

    if (
        colaborador is None
        and eh_administrador()
    ):
        colaborador = (
            Colaborador.query
            .filter_by(
                empresa_id=current_user.empresa_id,
                ativo=True,
            )
            .order_by(
                Colaborador.nome.asc()
            )
            .first()
        )

    agora = datetime.now()

    hoje_inicio = agora.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    hoje_fim = (
        hoje_inicio
        + timedelta(days=1)
    )

    marcacoes = []

    if colaborador:
        marcacoes = (
            PontoMarcacao.query
            .filter(
                PontoMarcacao.empresa_id
                == current_user.empresa_id,
                PontoMarcacao.colaborador_id
                == colaborador.id,
                PontoMarcacao.capturado_em
                >= hoje_inicio,
                PontoMarcacao.capturado_em
                < hoje_fim,
            )
            .order_by(
                PontoMarcacao.capturado_em.asc()
            )
            .all()
        )

    proximo_tipo = None

    if (
        colaborador
        and len(marcacoes)
        < len(SEQUENCIA_PONTO)
    ):
        proximo_tipo = SEQUENCIA_PONTO[
            len(marcacoes)
        ]

    return render_template(
        "ponto/coleta.html",
        colaborador=colaborador,
        marcacoes=marcacoes,
        tipos=TIPOS_PONTO,
        proximo_tipo=proximo_tipo,
        proximo_tipo_nome=(
            TIPOS_PONTO.get(proximo_tipo)
            if proximo_tipo
            else None
        ),
    )


def obter_data_filtro_gestao():
    data_texto = (
        request.args.get("data")
        or datetime.now().strftime("%Y-%m-%d")
    )

    try:
        data_filtro = datetime.strptime(
            data_texto,
            "%Y-%m-%d",
        )
    except ValueError:
        data_filtro = datetime.now()

    return data_filtro.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def listar_colaboradores_gestao():
    return (
        Colaborador.query
        .filter_by(
            empresa_id=current_user.empresa_id,
        )
        .order_by(
            Colaborador.ativo.desc(),
            Colaborador.nome.asc(),
        )
        .all()
    )


def obter_colaborador_filtro_gestao():
    colaborador_id = request.args.get(
        "colaborador_id",
        type=int,
    )

    if colaborador_id is None:
        return None

    return (
        Colaborador.query
        .filter_by(
            id=colaborador_id,
            empresa_id=current_user.empresa_id,
        )
        .first_or_404()
    )


def consulta_marcacoes_gestao(
    inicio,
    colaborador_filtro=None,
):
    fim = inicio + timedelta(days=1)

    consulta = (
        PontoMarcacao.query
        .options(
            joinedload(PontoMarcacao.colaborador),
            joinedload(PontoMarcacao.local_trabalho),
        )
        .filter(
            PontoMarcacao.empresa_id
            == current_user.empresa_id,
            PontoMarcacao.capturado_em
            >= inicio,
            PontoMarcacao.capturado_em
            < fim,
        )
    )

    if colaborador_filtro is not None:
        consulta = consulta.filter(
            PontoMarcacao.colaborador_id
            == colaborador_filtro.id,
        )

    return consulta


def descricao_localizacao_pdf(marcacao):
    if marcacao.dentro_geocerca is True:
        situacao = "Dentro da área"
    elif marcacao.dentro_geocerca is False:
        situacao = "Fora da área"
    elif marcacao.local_trabalho is None:
        situacao = "Local não configurado"
    else:
        situacao = "Não validado"

    coordenadas = ""
    if (
        marcacao.latitude is not None
        and marcacao.longitude is not None
    ):
        coordenadas = (
            f"\n{marcacao.latitude:.6f}, "
            f"{marcacao.longitude:.6f}"
        )

    return f"{situacao}{coordenadas}"


def desenhar_rodape_relatorio_pdf(canvas, documento):
    largura, _ = landscape(A4)

    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D9DEE5"))
    canvas.line(
        12 * mm,
        12 * mm,
        largura - 12 * mm,
        12 * mm,
    )
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.setFont("Helvetica", 8)
    canvas.drawString(
        12 * mm,
        7.5 * mm,
        "Relatório operacional — Gestão de Frota",
    )
    canvas.drawRightString(
        largura - 12 * mm,
        7.5 * mm,
        f"Página {documento.page}",
    )
    canvas.restoreState()


def gerar_relatorio_gestao_ponto_pdf(
    marcacoes,
    data_filtro,
    colaborador_filtro,
):
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=18 * mm,
        title="Relatório operacional de marcações",
        author="Gestão de Frota",
    )

    estilos_base = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "TituloRelatorioPonto",
        parent=estilos_base["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.white,
        alignment=TA_LEFT,
        spaceAfter=0,
    )
    estilo_subtitulo = ParagraphStyle(
        "SubtituloRelatorioPonto",
        parent=estilos_base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#DBE4F0"),
        alignment=TA_LEFT,
    )
    estilo_rotulo = ParagraphStyle(
        "RotuloRelatorioPonto",
        parent=estilos_base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#6B7280"),
    )
    estilo_valor = ParagraphStyle(
        "ValorRelatorioPonto",
        parent=estilos_base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#111827"),
    )
    estilo_cabecalho = ParagraphStyle(
        "CabecalhoTabelaPonto",
        parent=estilos_base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    estilo_celula = ParagraphStyle(
        "CelulaTabelaPonto",
        parent=estilos_base["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#111827"),
    )
    estilo_celula_centro = ParagraphStyle(
        "CelulaTabelaPontoCentro",
        parent=estilo_celula,
        alignment=TA_CENTER,
    )
    estilo_secao = ParagraphStyle(
        "SecaoRelatorioPonto",
        parent=estilos_base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#111827"),
        spaceBefore=4,
        spaceAfter=8,
    )

    empresa = current_user.empresa
    empresa_nome = (
        empresa.nome_fantasia
        or empresa.razao_social
    )
    empresa_documento = empresa.cnpj or "CNPJ não informado"
    colaborador_nome = (
        colaborador_filtro.nome
        if colaborador_filtro is not None
        else "Todos os colaboradores"
    )
    gerado_por = current_user.nome or current_user.usuario
    colaboradores_com_marcacao = len({
        marcacao.colaborador_id
        for marcacao in marcacoes
    })

    def paragrafo(valor, estilo=estilo_celula):
        texto = "—" if valor in (None, "") else str(valor)
        texto = escape(texto).replace("\n", "<br/>")
        return Paragraph(texto, estilo)

    elementos = []

    cabecalho = Table(
        [[
            Paragraph(
                "Relatório operacional de marcações",
                estilo_titulo,
            ),
            Paragraph(
                "Gestão de Frota<br/>Uso interno da operação",
                estilo_subtitulo,
            ),
        ]],
        colWidths=[178 * mm, 68 * mm],
    )
    cabecalho.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0F172A")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    elementos.append(cabecalho)
    elementos.append(Spacer(1, 7 * mm))

    resumo = Table(
        [[
            [
                Paragraph("EMPRESA", estilo_rotulo),
                Paragraph(escape(empresa_nome), estilo_valor),
                Paragraph(escape(empresa_documento), estilo_rotulo),
            ],
            [
                Paragraph("DATA", estilo_rotulo),
                Paragraph(
                    data_filtro.strftime("%d/%m/%Y"),
                    estilo_valor,
                ),
            ],
            [
                Paragraph("COLABORADOR", estilo_rotulo),
                Paragraph(escape(colaborador_nome), estilo_valor),
            ],
            [
                Paragraph("RESUMO", estilo_rotulo),
                Paragraph(
                    f"{len(marcacoes)} marcação(ões) · "
                    f"{colaboradores_com_marcacao} colaborador(es)",
                    estilo_valor,
                ),
            ],
        ]],
        colWidths=[77 * mm, 40 * mm, 77 * mm, 52 * mm],
    )
    resumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F5F7")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D9DEE5")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9DEE5")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    elementos.append(resumo)
    elementos.append(Spacer(1, 7 * mm))
    elementos.append(
        Paragraph("Marcações encontradas", estilo_secao)
    )

    dados_tabela = [[
        Paragraph("Horário", estilo_cabecalho),
        Paragraph("Colaborador", estilo_cabecalho),
        Paragraph("Matrícula", estilo_cabecalho),
        Paragraph("Tipo", estilo_cabecalho),
        Paragraph("Localização", estilo_cabecalho),
        Paragraph("Precisão", estilo_cabecalho),
        Paragraph("Sincronização", estilo_cabecalho),
    ]]

    for marcacao in marcacoes:
        precisao = (
            f"{marcacao.precisao_metros:.0f} m"
            if marcacao.precisao_metros is not None
            else "—"
        )
        dados_tabela.append([
            paragrafo(
                marcacao.capturado_em.strftime("%H:%M:%S"),
                estilo_celula_centro,
            ),
            paragrafo(marcacao.colaborador.nome),
            paragrafo(marcacao.colaborador.matricula),
            paragrafo(TIPOS_PONTO.get(
                marcacao.tipo,
                marcacao.tipo,
            )),
            paragrafo(descricao_localizacao_pdf(marcacao)),
            paragrafo(precisao, estilo_celula_centro),
            paragrafo(
                marcacao.status_sincronizacao,
                estilo_celula_centro,
            ),
        ])

    if len(dados_tabela) == 1:
        dados_tabela.append([
            paragrafo("Nenhuma marcação encontrada para os filtros."),
            "",
            "",
            "",
            "",
            "",
            "",
        ])

    tabela = LongTable(
        dados_tabela,
        colWidths=[22 * mm, 49 * mm, 27 * mm, 35 * mm, 57 * mm, 24 * mm, 32 * mm],
        repeatRows=1,
    )
    estilo_tabela = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9DEE5")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for indice in range(1, len(dados_tabela)):
        if indice % 2 == 0:
            estilo_tabela.append((
                "BACKGROUND",
                (0, indice),
                (-1, indice),
                colors.HexColor("#F8FAFC"),
            ))
    if len(dados_tabela) == 2 and not marcacoes:
        estilo_tabela.append(("SPAN", (0, 1), (-1, 1)))
        estilo_tabela.append(("ALIGN", (0, 1), (-1, 1), "CENTER"))
    tabela.setStyle(TableStyle(estilo_tabela))
    elementos.append(tabela)

    observacoes = [
        marcacao
        for marcacao in marcacoes
        if marcacao.observacao
    ]
    if observacoes:
        elementos.append(Spacer(1, 7 * mm))
        elementos.append(
            Paragraph("Observações e correções", estilo_secao)
        )
        dados_observacoes = [[
            Paragraph("Horário", estilo_cabecalho),
            Paragraph("Colaborador", estilo_cabecalho),
            Paragraph("Observação", estilo_cabecalho),
        ]]
        for marcacao in observacoes:
            dados_observacoes.append([
                paragrafo(
                    marcacao.capturado_em.strftime("%H:%M:%S"),
                    estilo_celula_centro,
                ),
                paragrafo(marcacao.colaborador.nome),
                paragrafo(marcacao.observacao),
            ])

        tabela_observacoes = LongTable(
            dados_observacoes,
            colWidths=[27 * mm, 55 * mm, 164 * mm],
            repeatRows=1,
        )
        tabela_observacoes.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9DEE5")),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elementos.append(tabela_observacoes)

    elementos.append(Spacer(1, 6 * mm))
    elementos.append(paragrafo(
        "Gerado em "
        f"{datetime.now().strftime('%d/%m/%Y às %H:%M:%S')} "
        f"por {gerado_por}.",
    ))

    documento.build(
        elementos,
        onFirstPage=desenhar_rodape_relatorio_pdf,
        onLaterPages=desenhar_rodape_relatorio_pdf,
    )
    buffer.seek(0)
    return buffer


@ponto_bp.route("/ponto-eletronico/gestao")
@login_required
def gestao():
    data_filtro = obter_data_filtro_gestao()
    colaborador_filtro = obter_colaborador_filtro_gestao()
    colaboradores = listar_colaboradores_gestao()

    marcacoes = (
        consulta_marcacoes_gestao(
            data_filtro,
            colaborador_filtro,
        )
        .order_by(
            PontoMarcacao.capturado_em.desc(),
        )
        .all()
    )

    return render_template(
        "ponto/gestao.html",
        marcacoes=marcacoes,
        data_filtro=data_filtro.date(),
        colaboradores=colaboradores,
        colaborador_filtro=colaborador_filtro,
        quantidade_colaboradores=len({
            marcacao.colaborador_id
            for marcacao in marcacoes
        }),
        tipos=TIPOS_PONTO,
    )


@ponto_bp.route(
    "/ponto-eletronico/gestao/relatorio.pdf"
)
@login_required
def exportar_gestao_ponto_pdf():
    data_filtro = obter_data_filtro_gestao()
    colaborador_filtro = obter_colaborador_filtro_gestao()

    marcacoes = (
        consulta_marcacoes_gestao(
            data_filtro,
            colaborador_filtro,
        )
        .order_by(
            PontoMarcacao.capturado_em.asc(),
        )
        .all()
    )

    arquivo = gerar_relatorio_gestao_ponto_pdf(
        marcacoes,
        data_filtro,
        colaborador_filtro,
    )
    sufixo_colaborador = (
        f"-colaborador-{colaborador_filtro.id}"
        if colaborador_filtro is not None
        else "-todos"
    )
    nome_arquivo = (
        "relatorio-marcacoes-"
        f"{data_filtro.strftime('%Y-%m-%d')}"
        f"{sufixo_colaborador}.pdf"
    )

    return send_file(
        arquivo,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=nome_arquivo,
        max_age=0,
    )



@ponto_bp.route(
    "/ponto-eletronico/gestao/<int:marcacao_id>/editar",
    methods=["POST"],
)
@login_required
def editar_marcacao_ponto(marcacao_id):
    if not eh_administrador():
        flash(
            "A correção de marcações é permitida "
            "somente para administradores.",
            "warning",
        )

        return redirect(
            url_for("ponto.gestao")
        )

    filtro_data = (
        request.form
        .get("filtro_data", "")
        .strip()
    )
    try:
        datetime.strptime(
            filtro_data,
            "%Y-%m-%d",
        )
    except ValueError:
        filtro_data = ""

    filtro_colaborador_id = request.form.get(
        "filtro_colaborador_id",
        type=int,
    )
    if filtro_colaborador_id is not None:
        colaborador_filtro_valido = (
            Colaborador.query
            .filter_by(
                id=filtro_colaborador_id,
                empresa_id=current_user.empresa_id,
            )
            .first()
        )
        if colaborador_filtro_valido is None:
            filtro_colaborador_id = None

    marcacao = (
        PontoMarcacao.query
        .filter_by(
            id=marcacao_id,
            empresa_id=current_user.empresa_id,
        )
        .first_or_404()
    )

    tipo = (
        request.form
        .get("tipo", "")
        .strip()
        .lower()
    )

    data_hora_texto = (
        request.form
        .get("capturado_em", "")
        .strip()
    )

    motivo = (
        request.form
        .get("motivo", "")
        .strip()
    )

    if tipo not in TIPOS_PONTO:
        flash(
            "Selecione um tipo de marcação válido.",
            "warning",
        )

        return redirect(
            request.referrer
            or url_for("ponto.gestao")
        )

    try:
        nova_data_hora = datetime.fromisoformat(
            data_hora_texto
        )

    except (TypeError, ValueError):
        flash(
            "Informe uma data e um horário válidos.",
            "warning",
        )

        return redirect(
            request.referrer
            or url_for("ponto.gestao")
        )

    if len(motivo) < 5:
        flash(
            "Informe o motivo da correção "
            "com pelo menos 5 caracteres.",
            "warning",
        )

        return redirect(
            request.referrer
            or url_for("ponto.gestao")
        )

    inicio_dia = nova_data_hora.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    fim_dia = (
        inicio_dia
        + timedelta(days=1)
    )

    marcacao_duplicada = (
        PontoMarcacao.query
        .filter(
            PontoMarcacao.empresa_id
            == current_user.empresa_id,
            PontoMarcacao.colaborador_id
            == marcacao.colaborador_id,
            PontoMarcacao.tipo
            == tipo,
            PontoMarcacao.capturado_em
            >= inicio_dia,
            PontoMarcacao.capturado_em
            < fim_dia,
            PontoMarcacao.id
            != marcacao.id,
        )
        .first()
    )

    if marcacao_duplicada:
        flash(
            "Este colaborador já possui uma marcação "
            f"de {TIPOS_PONTO[tipo]} nessa data.",
            "warning",
        )

        return redirect(
            request.referrer
            or url_for("ponto.gestao")
        )

    tipo_anterior = marcacao.tipo
    data_hora_anterior = marcacao.capturado_em

    responsavel = (
        current_user.nome
        or current_user.usuario
    )

    descricao_ajuste = (
        "\n"
        f"[CORREÇÃO EM "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} "
        f"POR {responsavel}] "
        f"{TIPOS_PONTO.get(tipo_anterior, tipo_anterior)} "
        f"em {data_hora_anterior.strftime('%d/%m/%Y %H:%M:%S')} "
        f"alterado para "
        f"{TIPOS_PONTO.get(tipo, tipo)} "
        f"em {nova_data_hora.strftime('%d/%m/%Y %H:%M:%S')}. "
        f"Motivo: {motivo}"
    )

    try:
        marcacao.tipo = tipo
        marcacao.capturado_em = nova_data_hora

        marcacao.observacao = (
            f"{marcacao.observacao or ''}"
            f"{descricao_ajuste}"
        ).strip()

        db.session.commit()

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Erro ao corrigir marcação do ponto"
        )

        flash(
            "Não foi possível atualizar a marcação.",
            "danger",
        )

        return redirect(
            request.referrer
            or url_for("ponto.gestao")
        )

    flash(
        "Marcação corrigida com sucesso.",
        "success",
    )

    parametros_retorno = {
        "data": (
            filtro_data
            or nova_data_hora.strftime("%Y-%m-%d")
        ),
    }
    if filtro_colaborador_id is not None:
        parametros_retorno["colaborador_id"] = (
            filtro_colaborador_id
        )

    return redirect(
        url_for(
            "ponto.gestao",
            **parametros_retorno,
        )
    )


@ponto_bp.route("/api/ponto/registrar", methods=["POST"])
@login_required
def api_registrar():
    colaborador_id = request.form.get("colaborador_id")
    colaborador = colaborador_do_usuario()

    if colaborador is None and eh_administrador() and colaborador_id:
        colaborador = Colaborador.query.filter_by(
            id=int(colaborador_id),
            empresa_id=current_user.empresa_id,
            ativo=True,
        ).first()

    if colaborador is None:
        return jsonify({"ok": False, "erro": "Usuário não vinculado a um colaborador."}), 403

    client_uuid = (
        request.form
        .get("client_uuid", "")
        .strip()
        or str(uuid.uuid4())
    )

    existente = (
        PontoMarcacao.query
        .filter_by(
            client_uuid=client_uuid
        )
        .first()
    )

    if existente:
        return jsonify({
            "ok": True,
            "duplicado": True,
            "id": existente.id,
            "tipo": TIPOS_PONTO.get(
                existente.tipo,
                existente.tipo,
            ),
            "capturado_em": (
                existente
                .capturado_em
                .isoformat()
            ),
        })

    latitude = parse_float(
        request.form.get("latitude")
    )

    longitude = parse_float(
        request.form.get("longitude")
    )

    precisao = parse_float(
        request.form.get(
            "precisao_metros"
        )
    )

    capturado_em = parse_datetime(
        request.form.get("capturado_em")
    )

    tipo = obter_proximo_tipo_ponto(
        colaborador_id=colaborador.id,
        data_referencia=capturado_em,
    )

    if tipo is None:
        return jsonify({
            "ok": False,
            "erro": (
                "As quatro marcações do dia "
                "já foram registradas."
            ),
        }), 409

    local = colaborador.local_trabalho
    distancia = None
    dentro_geocerca = None
    if local and local.latitude is not None and local.longitude is not None:
        distancia = distancia_metros(
            latitude,
            longitude,
            local.latitude,
            local.longitude,
        )
        if distancia is not None:
            dentro_geocerca = distancia <= local.raio_metros

    try:
        foto_path = salvar_foto(
            arquivo=request.files.get("foto"),
            empresa_id=current_user.empresa_id,
            colaborador=colaborador,
            client_uuid=client_uuid,
            capturado_em=capturado_em,
            latitude=latitude,
            longitude=longitude,
            precisao=precisao,
            dentro_geocerca=dentro_geocerca,
            distancia=distancia,
        )
    except ValueError as erro:
        return jsonify({"ok": False, "erro": str(erro)}), 400

    marcacao = PontoMarcacao(
        client_uuid=client_uuid,
        tipo=tipo,
        capturado_em=capturado_em,
        recebido_em=datetime.utcnow(),
        latitude=latitude,
        longitude=longitude,
        precisao_metros=precisao,
        distancia_local_metros=distancia,
        dentro_geocerca=dentro_geocerca,
        foto_path=foto_path,
        dispositivo_id=request.form.get("dispositivo_id", "").strip() or None,
        dispositivo_info=request.form.get("dispositivo_info", "").strip() or request.user_agent.string[:300],
        ip_origem=request.headers.get("X-Forwarded-For", request.remote_addr),
        status_sincronizacao="Sincronizado",
        observacao=request.form.get("observacao", "").strip() or None,
        empresa_id=current_user.empresa_id,
        colaborador_id=colaborador.id,
        local_trabalho_id=local.id if local else None,
    )
    db.session.add(marcacao)
    db.session.commit()

    return jsonify({
        "ok": True,
        "id": marcacao.id,
        "tipo": TIPOS_PONTO[tipo],
        "capturado_em": marcacao.capturado_em.isoformat(),
        "recebido_em": marcacao.recebido_em.isoformat(),
        "dentro_geocerca": marcacao.dentro_geocerca,
        "distancia_local_metros": round(distancia, 1) if distancia is not None else None,
    }), 201


@ponto_bp.route("/api/ponto/meus-registros")
@login_required
def api_meus_registros():
    colaborador = colaborador_do_usuario()
    if colaborador is None:
        return jsonify({"ok": False, "erro": "Usuário não vinculado."}), 403

    itens = PontoMarcacao.query.filter_by(
        empresa_id=current_user.empresa_id,
        colaborador_id=colaborador.id,
    ).order_by(PontoMarcacao.capturado_em.desc()).limit(100).all()

    return jsonify({
        "ok": True,
        "registros": [
            {
                "id": item.id,
                "client_uuid": item.client_uuid,
                "tipo": item.tipo,
                "capturado_em": item.capturado_em.isoformat(),
                "recebido_em": item.recebido_em.isoformat(),
                "latitude": item.latitude,
                "longitude": item.longitude,
                "precisao_metros": item.precisao_metros,
                "dentro_geocerca": item.dentro_geocerca,
            }
            for item in itens
        ],
    })
