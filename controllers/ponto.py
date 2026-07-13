import math
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont, ImageOps

from database.models import Colaborador, LocalTrabalho, PontoMarcacao, Usuario
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

        try:
            colaborador = Colaborador(
                empresa_id=current_user.empresa_id,
                nome=nome,
                matricula=matricula,
                funcao=funcao,
                telefone=telefone,
                usuario_id=int(usuario_id) if usuario_id else None,
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

    return render_template(
        "cadastros/colaboradores.html",
        colaboradores=itens,
        usuarios=usuarios,
        locais=locais,
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

    try:
        colaborador.nome = nome
        colaborador.matricula = matricula
        colaborador.funcao = funcao
        colaborador.telefone = telefone
        colaborador.usuario_id = int(usuario_id) if usuario_id else None
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


@ponto_bp.route("/ponto-eletronico/gestao")
@login_required
def gestao():
    data_texto = request.args.get("data") or datetime.now().strftime("%Y-%m-%d")
    try:
        data_filtro = datetime.strptime(data_texto, "%Y-%m-%d")
    except ValueError:
        data_filtro = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    inicio = data_filtro.replace(hour=0, minute=0, second=0, microsecond=0)
    fim = inicio + timedelta(days=1)
    marcacoes = PontoMarcacao.query.filter(
        PontoMarcacao.empresa_id == current_user.empresa_id,
        PontoMarcacao.capturado_em >= inicio,
        PontoMarcacao.capturado_em < fim,
    ).order_by(PontoMarcacao.capturado_em.desc()).all()

    return render_template(
        "ponto/gestao.html",
        marcacoes=marcacoes,
        data_filtro=inicio.date(),
        tipos=TIPOS_PONTO,
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

    return redirect(
        url_for(
            "ponto.gestao",
            data=nova_data_hora.strftime(
                "%Y-%m-%d"
            ),
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