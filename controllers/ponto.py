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

from database.models import Colaborador, LocalTrabalho, PontoMarcacao, Usuario
from extensions import db


ponto_bp = Blueprint("ponto", __name__)

TIPOS_PONTO = {
    "entrada": "Entrada",
    "intervalo": "Início do intervalo",
    "retorno": "Retorno do intervalo",
    "saida": "Saída",
}

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


def salvar_foto(arquivo, empresa_id, colaborador_id, client_uuid):
    if arquivo is None or not arquivo.filename:
        raise ValueError("A foto facial é obrigatória.")

    extensao = arquivo.filename.rsplit(".", 1)[-1].lower() if "." in arquivo.filename else ""
    if extensao not in EXTENSOES_IMAGEM:
        raise ValueError("Envie uma imagem JPG, PNG, WEBP ou HEIC.")

    pasta_relativa = Path("uploads") / "ponto" / str(empresa_id) / str(colaborador_id)
    pasta_absoluta = Path(current_app.static_folder) / pasta_relativa
    pasta_absoluta.mkdir(parents=True, exist_ok=True)

    nome_original = secure_filename(arquivo.filename)
    nome = f"{client_uuid}_{nome_original or ('foto.' + extensao)}"
    caminho = pasta_absoluta / nome
    arquivo.save(caminho)

    return (pasta_relativa / nome).as_posix()


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


@ponto_bp.route("/ponto-eletronico")
@login_required
def coleta():
    colaborador = colaborador_do_usuario()
    if colaborador is None and eh_administrador():
        colaborador = Colaborador.query.filter_by(
            empresa_id=current_user.empresa_id,
            ativo=True,
        ).order_by(Colaborador.nome.asc()).first()

    hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    hoje_fim = hoje_inicio + timedelta(days=1)
    marcacoes = []
    if colaborador:
        marcacoes = PontoMarcacao.query.filter(
            PontoMarcacao.empresa_id == current_user.empresa_id,
            PontoMarcacao.colaborador_id == colaborador.id,
            PontoMarcacao.capturado_em >= hoje_inicio,
            PontoMarcacao.capturado_em < hoje_fim,
        ).order_by(PontoMarcacao.capturado_em.asc()).all()

    return render_template(
        "ponto/coleta.html",
        colaborador=colaborador,
        marcacoes=marcacoes,
        tipos=TIPOS_PONTO,
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

    tipo = request.form.get("tipo", "").strip().lower()
    if tipo not in TIPOS_PONTO:
        return jsonify({"ok": False, "erro": "Tipo de marcação inválido."}), 400

    client_uuid = request.form.get("client_uuid", "").strip() or str(uuid.uuid4())
    existente = PontoMarcacao.query.filter_by(client_uuid=client_uuid).first()
    if existente:
        return jsonify({
            "ok": True,
            "duplicado": True,
            "id": existente.id,
            "capturado_em": existente.capturado_em.isoformat(),
        })

    latitude = parse_float(request.form.get("latitude"))
    longitude = parse_float(request.form.get("longitude"))
    precisao = parse_float(request.form.get("precisao_metros"))
    capturado_em = parse_datetime(request.form.get("capturado_em"))

    try:
        foto_path = salvar_foto(
            request.files.get("foto"),
            current_user.empresa_id,
            colaborador.id,
            client_uuid,
        )
    except ValueError as erro:
        return jsonify({"ok": False, "erro": str(erro)}), 400

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
