import uuid
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func, or_
from werkzeug.utils import secure_filename

from controllers.ponto import (
    SEQUENCIA_PONTO,
    TIPOS_PONTO,
    distancia_metros,
    salvar_foto,
)
from database.models import (
    Abastecimento,
    Colaborador,
    DiarioBordo,
    Motorista,
    MovimentacaoMaterial,
    Obra,
    PontoMarcacao,
    Usuario,
    Veiculo,
)
from extensions import db


mobile_api_bp = Blueprint(
    "mobile_api",
    __name__,
    url_prefix="/api/mobile",
)

FUSO_LOCAL = ZoneInfo("America/Rio_Branco")
EXTENSOES_IMAGEM = {"jpg", "jpeg", "png", "webp"}
EXTENSOES_COMPROVANTE = EXTENSOES_IMAGEM | {"pdf"}
PERFIS_RECEBIMENTO_MATERIAL = {"apontador"}


@mobile_api_bp.errorhandler(413)
def arquivo_mobile_muito_grande(_erro):
    return jsonify({
        "ok": False,
        "erro": (
            "As fotos ultrapassaram o limite permitido. "
            "Tire novas fotos e tente novamente."
        ),
    }), 413


def agora_local():
    return datetime.now(FUSO_LOCAL).replace(tzinfo=None)


def serializador_token():
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"],
        salt="diario-de-bordo-mobile-v1",
    )


def criar_token_mobile(usuario):
    return serializador_token().dumps({
        "usuario_id": usuario.id,
        "senha_chave": usuario.senha_hash[-16:],
    })


def colaborador_do_usuario(usuario):
    return Colaborador.query.filter_by(
        empresa_id=usuario.empresa_id,
        usuario_id=usuario.id,
        ativo=True,
    ).first()


def parse_float(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def parse_datetime_local(valor):
    if not valor:
        return agora_local()

    texto = str(valor).strip().replace("Z", "+00:00")

    try:
        data = datetime.fromisoformat(texto)
    except ValueError:
        return agora_local()

    if data.tzinfo is not None:
        data = data.astimezone(FUSO_LOCAL).replace(tzinfo=None)

    return data


def intervalo_dia(data_referencia):
    inicio = data_referencia.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    return inicio, inicio + timedelta(days=1)


def registros_do_dia(usuario, colaborador, data_referencia=None):
    referencia = data_referencia or agora_local()
    inicio, fim = intervalo_dia(referencia)

    return (
        PontoMarcacao.query
        .filter(
            PontoMarcacao.empresa_id == usuario.empresa_id,
            PontoMarcacao.colaborador_id == colaborador.id,
            PontoMarcacao.capturado_em >= inicio,
            PontoMarcacao.capturado_em < fim,
        )
        .order_by(PontoMarcacao.capturado_em.asc())
        .all()
    )


def proximo_tipo(registros):
    if len(registros) >= len(SEQUENCIA_PONTO):
        return None

    return SEQUENCIA_PONTO[len(registros)]


def serializar_usuario(usuario):
    empresa = usuario.empresa

    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "usuario": usuario.usuario,
        "email": usuario.email,
        "perfil": usuario.perfil,
        "trocar_senha": usuario.trocar_senha,
        "pode_receber_materiais": (
            (usuario.perfil or "").strip().lower()
            in PERFIS_RECEBIMENTO_MATERIAL
        ),
        "empresa": {
            "id": empresa.id,
            "nome": empresa.nome_fantasia or empresa.razao_social,
        },
    }


def serializar_registro(registro):
    return {
        "id": registro.id,
        "client_uuid": registro.client_uuid,
        "tipo": registro.tipo,
        "tipo_descricao": TIPOS_PONTO.get(
            registro.tipo,
            registro.tipo,
        ),
        "capturado_em": registro.capturado_em.isoformat(),
        "recebido_em": registro.recebido_em.isoformat(),
        "latitude": registro.latitude,
        "longitude": registro.longitude,
        "precisao_metros": registro.precisao_metros,
        "dentro_geocerca": registro.dentro_geocerca,
        "distancia_local_metros": (
            round(registro.distancia_local_metros, 1)
            if registro.distancia_local_metros is not None
            else None
        ),
        "status_sincronizacao": registro.status_sincronizacao,
    }


def serializar_estado(usuario, colaborador):
    registros = registros_do_dia(usuario, colaborador)
    tipo = proximo_tipo(registros)
    local = colaborador.local_trabalho

    return {
        "data": agora_local().date().isoformat(),
        "colaborador": {
            "id": colaborador.id,
            "nome": colaborador.nome,
            "matricula": colaborador.matricula,
            "funcao": colaborador.funcao,
        },
        "local_trabalho": (
            {
                "id": local.id,
                "nome": local.nome,
                "endereco": local.endereco,
                "raio_metros": local.raio_metros,
            }
            if local
            else None
        ),
        "proximo_tipo": tipo,
        "proximo_tipo_descricao": (
            TIPOS_PONTO[tipo]
            if tipo
            else None
        ),
        "jornada_concluida": tipo is None,
        "total": len(registros),
        "registros": [
            serializar_registro(registro)
            for registro in registros
        ],
    }


def token_obrigatorio(funcao):
    @wraps(funcao)
    def wrapper(*args, **kwargs):
        cabecalho = request.headers.get("Authorization", "")
        esquema, _, token = cabecalho.partition(" ")

        if esquema.lower() != "bearer" or not token:
            return jsonify({
                "ok": False,
                "erro": "Token de acesso não informado.",
            }), 401

        try:
            payload = serializador_token().loads(
                token,
                max_age=current_app.config.get(
                    "MOBILE_TOKEN_MAX_AGE",
                    2592000,
                ),
            )
        except SignatureExpired:
            return jsonify({
                "ok": False,
                "erro": "Sua sessão expirou. Entre novamente.",
            }), 401
        except BadSignature:
            return jsonify({
                "ok": False,
                "erro": "Sessão inválida. Entre novamente.",
            }), 401

        if not isinstance(payload, dict) or not payload.get("usuario_id"):
            return jsonify({
                "ok": False,
                "erro": "Sessão inválida. Entre novamente.",
            }), 401

        usuario = db.session.get(
            Usuario,
            payload["usuario_id"],
        )

        if (
            usuario is None
            or not usuario.ativo
            or usuario.empresa is None
            or not usuario.empresa.ativa
        ):
            return jsonify({
                "ok": False,
                "erro": "Usuário não encontrado ou desativado.",
            }), 401

        if payload.get("senha_chave") != usuario.senha_hash[-16:]:
            return jsonify({
                "ok": False,
                "erro": "Sua sessão expirou. Entre novamente.",
            }), 401

        rotas_permitidas_na_troca = {
            "mobile_api.usuario_atual",
            "mobile_api.trocar_senha_mobile",
        }

        if (
            usuario.trocar_senha
            and request.endpoint not in rotas_permitidas_na_troca
        ):
            return jsonify({
                "ok": False,
                "codigo": "TROCA_SENHA_OBRIGATORIA",
                "erro": "Crie uma nova senha para continuar.",
            }), 403

        g.mobile_user = usuario
        return funcao(*args, **kwargs)

    return wrapper


@mobile_api_bp.get("/saude")
def saude():
    return jsonify({
        "ok": True,
        "status": "online",
        "servico": "Diário de Bordo Mobile",
    })


@mobile_api_bp.post("/auth/login")
def login():
    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        return jsonify({
            "ok": False,
            "erro": "Envie os dados de acesso em formato JSON.",
        }), 400

    identificacao = str(
        dados.get("usuario", "")
    ).strip().lower()
    senha = str(dados.get("senha", ""))

    if not identificacao or not senha:
        return jsonify({
            "ok": False,
            "erro": "Informe o usuário e a senha.",
        }), 400

    usuario = (
        Usuario.query
        .filter(
            or_(
                func.lower(Usuario.usuario) == identificacao,
                func.lower(Usuario.email) == identificacao,
            )
        )
        .first()
    )

    if usuario is None or not usuario.verificar_senha(senha):
        return jsonify({
            "ok": False,
            "erro": "Usuário ou senha inválidos.",
        }), 401

    if not usuario.ativo or not usuario.empresa.ativa:
        return jsonify({
            "ok": False,
            "erro": "Este usuário está desativado.",
        }), 403

    if not usuario.trocar_senha:
        usuario.ultimo_acesso = datetime.utcnow()
        db.session.commit()

    token = criar_token_mobile(usuario)

    colaborador = colaborador_do_usuario(usuario)

    return jsonify({
        "ok": True,
        "token": token,
        "expira_em_segundos": current_app.config.get(
            "MOBILE_TOKEN_MAX_AGE",
            2592000,
        ),
        "usuario": serializar_usuario(usuario),
        "colaborador_vinculado": colaborador is not None,
    })


@mobile_api_bp.get("/auth/me")
@token_obrigatorio
def usuario_atual():
    usuario = g.mobile_user
    colaborador = colaborador_do_usuario(usuario)

    return jsonify({
        "ok": True,
        "usuario": serializar_usuario(usuario),
        "colaborador_vinculado": colaborador is not None,
    })


@mobile_api_bp.post("/auth/trocar-senha")
@token_obrigatorio
def trocar_senha_mobile():
    usuario = g.mobile_user
    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        return jsonify({
            "ok": False,
            "erro": "Envie os dados da nova senha em formato JSON.",
        }), 400

    senha_atual = str(dados.get("senha_atual", ""))
    nova_senha = str(dados.get("nova_senha", ""))
    confirmar_senha = str(dados.get("confirmar_senha", ""))

    if not senha_atual or not nova_senha or not confirmar_senha:
        return jsonify({
            "ok": False,
            "erro": "Preencha todos os campos de senha.",
        }), 400

    if not usuario.verificar_senha(senha_atual):
        return jsonify({
            "ok": False,
            "erro": "A senha temporária informada está incorreta.",
        }), 400

    if len(nova_senha) < 8:
        return jsonify({
            "ok": False,
            "erro": "A nova senha deve possuir pelo menos 8 caracteres.",
        }), 400

    if nova_senha == senha_atual:
        return jsonify({
            "ok": False,
            "erro": "A nova senha deve ser diferente da senha temporária.",
        }), 400

    if nova_senha != confirmar_senha:
        return jsonify({
            "ok": False,
            "erro": "A confirmação não corresponde à nova senha.",
        }), 400

    usuario.definir_senha(nova_senha)
    usuario.trocar_senha = False
    usuario.ultimo_acesso = datetime.utcnow()
    db.session.commit()

    token = criar_token_mobile(usuario)
    colaborador = colaborador_do_usuario(usuario)

    return jsonify({
        "ok": True,
        "mensagem": "Senha alterada com sucesso.",
        "token": token,
        "expira_em_segundos": current_app.config.get(
            "MOBILE_TOKEN_MAX_AGE",
            2592000,
        ),
        "usuario": serializar_usuario(usuario),
        "colaborador_vinculado": colaborador is not None,
    })


@mobile_api_bp.get("/ponto/estado")
@token_obrigatorio
def estado_ponto():
    usuario = g.mobile_user
    colaborador = colaborador_do_usuario(usuario)

    if colaborador is None:
        return jsonify({
            "ok": False,
            "erro": "Seu usuário ainda não está vinculado a um colaborador ativo.",
        }), 403

    return jsonify({
        "ok": True,
        **serializar_estado(usuario, colaborador),
    })


@mobile_api_bp.post("/ponto/registrar")
@token_obrigatorio
def registrar_ponto():
    usuario = g.mobile_user
    colaborador = colaborador_do_usuario(usuario)

    if colaborador is None:
        return jsonify({
            "ok": False,
            "erro": "Seu usuário ainda não está vinculado a um colaborador ativo.",
        }), 403

    client_uuid = (
        request.form.get("client_uuid", "").strip()
        or str(uuid.uuid4())
    )

    if len(client_uuid) > 80:
        return jsonify({
            "ok": False,
            "erro": "Identificador do registro inválido.",
        }), 400

    existente = PontoMarcacao.query.filter_by(
        client_uuid=client_uuid,
        empresa_id=usuario.empresa_id,
        colaborador_id=colaborador.id,
    ).first()

    if existente:
        return jsonify({
            "ok": True,
            "duplicado": True,
            "registro": serializar_registro(existente),
        })

    latitude = parse_float(request.form.get("latitude"))
    longitude = parse_float(request.form.get("longitude"))
    precisao = parse_float(
        request.form.get("precisao_metros")
    )

    if latitude is None or longitude is None:
        return jsonify({
            "ok": False,
            "erro": "A localização do aparelho é obrigatória para registrar o ponto.",
        }), 400

    capturado_em = parse_datetime_local(
        request.form.get("capturado_em")
    )

    registros = registros_do_dia(
        usuario,
        colaborador,
        capturado_em,
    )
    tipo = proximo_tipo(registros)

    if tipo is None:
        return jsonify({
            "ok": False,
            "erro": "As quatro marcações do dia já foram registradas.",
        }), 409

    local = colaborador.local_trabalho
    distancia = None
    dentro_geocerca = None

    if (
        local
        and local.latitude is not None
        and local.longitude is not None
    ):
        distancia = distancia_metros(
            latitude,
            longitude,
            local.latitude,
            local.longitude,
        )

        if distancia is not None:
            dentro_geocerca = (
                distancia <= local.raio_metros
            )

    try:
        foto_path = salvar_foto(
            arquivo=request.files.get("foto"),
            empresa_id=usuario.empresa_id,
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
        return jsonify({
            "ok": False,
            "erro": str(erro),
        }), 400

    ip_encaminhado = request.headers.get("X-Forwarded-For", "")
    ip_origem = (
        ip_encaminhado.split(",")[0].strip()
        if ip_encaminhado
        else request.remote_addr
    )

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
        dispositivo_id=(
            request.form.get("dispositivo_id", "").strip()
            or None
        ),
        dispositivo_info=(
            request.form.get("dispositivo_info", "").strip()
            or request.user_agent.string[:300]
        ),
        ip_origem=ip_origem,
        status_sincronizacao="Sincronizado",
        observacao=(
            request.form.get("observacao", "").strip()
            or None
        ),
        empresa_id=usuario.empresa_id,
        colaborador_id=colaborador.id,
        local_trabalho_id=local.id if local else None,
    )

    db.session.add(marcacao)
    db.session.commit()

    return jsonify({
        "ok": True,
        "mensagem": f"{TIPOS_PONTO[tipo]} registrada com sucesso.",
        "registro": serializar_registro(marcacao),
        "estado": serializar_estado(usuario, colaborador),
    }), 201


def motorista_do_usuario(usuario):
    colaborador = colaborador_do_usuario(usuario)

    if colaborador is None:
        return None, (
            "Seu usuário ainda não está vinculado a um colaborador ativo."
        )

    motorista = colaborador.motorista

    if motorista is None:
        return None, (
            "O colaborador ainda não possui um motorista vinculado. "
            "Acesse Cadastros > Colaboradores no sistema web e selecione "
            "o motorista."
        )

    if motorista.empresa_id != usuario.empresa_id:
        return None, "O motorista vinculado pertence a outra empresa."

    if motorista.status != "Ativo":
        return None, "O cadastro desse motorista está inativo."

    return motorista, None


def converter_data_diario(valor):
    if not valor:
        return agora_local().date()

    try:
        return datetime.strptime(str(valor), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def converter_hora_diario(valor):
    if not valor:
        return agora_local().time().replace(second=0, microsecond=0)

    try:
        return datetime.strptime(str(valor), "%H:%M").time()
    except (TypeError, ValueError):
        return None


def converter_inteiro_diario(valor):
    if valor is None or str(valor).strip() == "":
        return None

    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def converter_decimal_diario(valor):
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


def calcular_total_abastecimento(litros, valor_litro):
    return (litros * valor_litro).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def extensao_arquivo(arquivo):
    if not arquivo or not arquivo.filename:
        return None

    nome = secure_filename(arquivo.filename)

    if "." not in nome:
        return None

    return nome.rsplit(".", 1)[1].lower()


def salvar_arquivo_abastecimento_mobile(
    arquivo,
    empresa_id,
    prefixo,
    extensoes,
):
    extensao = extensao_arquivo(arquivo)

    if extensao not in extensoes:
        raise ValueError("Formato de arquivo não permitido.")

    pasta_relativa = Path(
        "uploads",
        "abastecimentos",
        str(empresa_id),
    )
    pasta_absoluta = Path(current_app.static_folder) / pasta_relativa
    pasta_absoluta.mkdir(parents=True, exist_ok=True)

    nome_final = f"{prefixo}-mobile-{uuid.uuid4().hex}.{extensao}"
    arquivo.save(pasta_absoluta / nome_final)

    return (pasta_relativa / nome_final).as_posix()


def salvar_foto_recebimento_material(arquivo, empresa_id):
    extensao = extensao_arquivo(arquivo)

    if extensao not in EXTENSOES_IMAGEM:
        raise ValueError("A foto do material deve ser JPG, PNG ou WEBP.")

    pasta_relativa = Path(
        "uploads",
        "materiais",
        str(empresa_id),
    )
    pasta_absoluta = Path(current_app.static_folder) / pasta_relativa
    pasta_absoluta.mkdir(parents=True, exist_ok=True)

    nome_final = f"recebimento-{uuid.uuid4().hex}.{extensao}"
    arquivo.save(pasta_absoluta / nome_final)

    return (pasta_relativa / nome_final).as_posix()


def remover_arquivo_mobile(caminho_relativo):
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


def serializar_obra(obra):
    return {
        "id": obra.id,
        "codigo": obra.codigo,
        "nome": obra.nome,
    }


def serializar_veiculo_diario(veiculo):
    return {
        "id": veiculo.id,
        "placa": veiculo.placa,
        "modelo": veiculo.modelo,
        "km_atual": veiculo.km_atual,
        "combustivel": veiculo.combustivel,
        "obra_id": veiculo.obra_id,
    }


def serializar_movimentacao_resumida(movimentacao):
    if movimentacao is None:
        return None

    return {
        "id": movimentacao.id,
        "material": movimentacao.material,
        "numero_movimentacao": movimentacao.numero_movimentacao,
        "quantidade": (
            float(movimentacao.quantidade)
            if movimentacao.quantidade is not None
            else None
        ),
        "unidade": movimentacao.unidade,
        "observacao_carga": movimentacao.observacao_carga,
        "status": movimentacao.status,
        "recebido_em": (
            movimentacao.recebido_em.isoformat()
            if movimentacao.recebido_em
            else None
        ),
    }


def serializar_movimentacao_material(movimentacao):
    diario = movimentacao.diario_bordo

    return {
        **serializar_movimentacao_resumida(movimentacao),
        "criado_em": movimentacao.criado_em.isoformat(),
        "observacao_recebimento": movimentacao.observacao_recebimento,
        "foto_recebimento": movimentacao.foto_recebimento,
        "latitude_recebimento": movimentacao.latitude_recebimento,
        "longitude_recebimento": movimentacao.longitude_recebimento,
        "precisao_metros": movimentacao.precisao_metros,
        "recebido_por": (
            {
                "id": movimentacao.recebido_por.id,
                "nome": movimentacao.recebido_por.nome,
            }
            if movimentacao.recebido_por
            else None
        ),
        "diario": {
            "id": diario.id,
            "data": diario.data.isoformat(),
            "hora_saida": diario.hora_saida.strftime("%H:%M"),
            "origem": diario.origem,
            "destino": diario.destino,
            "status": diario.status,
            "veiculo": serializar_veiculo_diario(diario.veiculo),
            "motorista": {
                "id": diario.motorista.id,
                "nome": diario.motorista.nome,
            },
            "obra": serializar_obra(diario.obra) if diario.obra else None,
        },
    }


def serializar_diario(diario):
    return {
        "id": diario.id,
        "data": diario.data.isoformat(),
        "hora_saida": diario.hora_saida.strftime("%H:%M"),
        "hora_chegada": (
            diario.hora_retorno.strftime("%H:%M")
            if diario.hora_retorno
            else None
        ),
        "km_inicial": diario.km_inicial,
        "km_final": diario.km_final,
        "km_percorrida": diario.km_percorrida,
        "origem": diario.origem,
        "destino": diario.destino,
        "finalidade": diario.finalidade,
        "ocorrencias": diario.ocorrencias,
        "status": diario.status,
        "veiculo": serializar_veiculo_diario(diario.veiculo),
        "motorista": {
            "id": diario.motorista.id,
            "nome": diario.motorista.nome,
        },
        "obra": serializar_obra(diario.obra) if diario.obra else None,
        "houve_abastecimento": bool(diario.abastecimentos),
        "movimentacao_material": serializar_movimentacao_resumida(
            diario.movimentacao_material
        ),
    }


def diario_aberto_motorista(usuario, motorista):
    return DiarioBordo.query.filter_by(
        empresa_id=usuario.empresa_id,
        motorista_id=motorista.id,
        status="Em andamento",
    ).first()


def diario_aberto_veiculo(usuario, veiculo_id):
    if not veiculo_id:
        return None

    return DiarioBordo.query.filter_by(
        empresa_id=usuario.empresa_id,
        veiculo_id=veiculo_id,
        status="Em andamento",
    ).first()


def serializar_estado_diario(usuario, motorista):
    diario_aberto = diario_aberto_motorista(usuario, motorista)
    veiculo = motorista.veiculo
    bloqueio = None

    if diario_aberto is None:
        if veiculo is None:
            bloqueio = (
                "Você ainda não possui um veículo vinculado. "
                "Atualize o cadastro do motorista no sistema web."
            )
        elif veiculo.status != "Ativo":
            bloqueio = "O veículo vinculado está inativo."
        else:
            conflito = diario_aberto_veiculo(
                usuario,
                veiculo.id,
            )

            if conflito:
                bloqueio = (
                    "O veículo vinculado já possui outro diário em andamento."
                )

    obras = Obra.query.filter_by(
        empresa_id=usuario.empresa_id,
    ).order_by(Obra.nome.asc()).all()

    recentes = DiarioBordo.query.filter_by(
        empresa_id=usuario.empresa_id,
        motorista_id=motorista.id,
    ).order_by(
        DiarioBordo.data.desc(),
        DiarioBordo.hora_saida.desc(),
        DiarioBordo.id.desc(),
    ).limit(8).all()

    return {
        "motorista": {
            "id": motorista.id,
            "nome": motorista.nome,
        },
        "veiculo": (
            serializar_veiculo_diario(veiculo)
            if veiculo
            else None
        ),
        "obras": [serializar_obra(obra) for obra in obras],
        "diario_em_andamento": (
            serializar_diario(diario_aberto)
            if diario_aberto
            else None
        ),
        "pode_iniciar": diario_aberto is None and bloqueio is None,
        "bloqueio": bloqueio,
        "recentes": [serializar_diario(diario) for diario in recentes],
    }


def obter_obra_mobile(usuario, obra_id):
    if obra_id in (None, ""):
        return None, None

    try:
        obra_id = int(obra_id)
    except (TypeError, ValueError):
        return None, "A obra selecionada é inválida."

    obra = Obra.query.filter_by(
        id=obra_id,
        empresa_id=usuario.empresa_id,
    ).first()

    if obra is None:
        return None, "A obra selecionada não foi encontrada."

    return obra, None


def usuario_pode_receber_material(usuario):
    return (
        (usuario.perfil or "").strip().lower()
        in PERFIS_RECEBIMENTO_MATERIAL
    )


def validar_permissao_recebimento(usuario):
    if usuario_pode_receber_material(usuario):
        return None

    return jsonify({
        "ok": False,
        "erro": "Seu perfil não possui permissão para receber materiais.",
    }), 403


@mobile_api_bp.get("/materiais/pendentes")
@token_obrigatorio
def materiais_pendentes():
    usuario = g.mobile_user
    erro_permissao = validar_permissao_recebimento(usuario)

    if erro_permissao:
        return erro_permissao

    busca = request.args.get("busca", "").strip()
    consulta = (
        MovimentacaoMaterial.query
        .filter_by(
            empresa_id=usuario.empresa_id,
            status="Em trânsito",
        )
        .join(MovimentacaoMaterial.diario_bordo)
        .join(DiarioBordo.veiculo)
    )

    if busca:
        termo = f"%{busca}%"
        consulta = consulta.filter(
            or_(
                Veiculo.placa.ilike(termo),
                MovimentacaoMaterial.material.ilike(termo),
                MovimentacaoMaterial.numero_movimentacao.ilike(termo),
            )
        )

    itens = consulta.order_by(
        DiarioBordo.data.asc(),
        DiarioBordo.hora_saida.asc(),
        MovimentacaoMaterial.id.asc(),
    ).all()

    return jsonify({
        "ok": True,
        "total": len(itens),
        "movimentacoes": [
            serializar_movimentacao_material(item)
            for item in itens
        ],
    })


@mobile_api_bp.get("/materiais/historico")
@token_obrigatorio
def historico_materiais():
    usuario = g.mobile_user
    erro_permissao = validar_permissao_recebimento(usuario)

    if erro_permissao:
        return erro_permissao

    itens = (
        MovimentacaoMaterial.query
        .filter(
            MovimentacaoMaterial.empresa_id == usuario.empresa_id,
            MovimentacaoMaterial.recebido_por_id == usuario.id,
            MovimentacaoMaterial.status.in_([
                "Recebido",
                "Recebido com ressalva",
            ]),
        )
        .order_by(
            MovimentacaoMaterial.recebido_em.desc(),
            MovimentacaoMaterial.id.desc(),
        )
        .limit(100)
        .all()
    )

    return jsonify({
        "ok": True,
        "total": len(itens),
        "movimentacoes": [
            serializar_movimentacao_material(item)
            for item in itens
        ],
    })


@mobile_api_bp.post("/materiais/<int:movimentacao_id>/receber")
@token_obrigatorio
def receber_material(movimentacao_id):
    usuario = g.mobile_user
    erro_permissao = validar_permissao_recebimento(usuario)

    if erro_permissao:
        return erro_permissao

    client_uuid = request.form.get("client_uuid", "").strip()

    if not client_uuid:
        return jsonify({
            "ok": False,
            "erro": "Identificador do recebimento não informado.",
        }), 400

    existente = MovimentacaoMaterial.query.filter_by(
        empresa_id=usuario.empresa_id,
        client_uuid_recebimento=client_uuid,
    ).first()

    if existente:
        return jsonify({
            "ok": True,
            "mensagem": "Esse recebimento já foi confirmado.",
            "movimentacao": serializar_movimentacao_material(existente),
        })

    movimentacao = MovimentacaoMaterial.query.filter_by(
        id=movimentacao_id,
        empresa_id=usuario.empresa_id,
    ).first()

    if movimentacao is None:
        return jsonify({
            "ok": False,
            "erro": "Movimentação de material não encontrada.",
        }), 404

    if movimentacao.status != "Em trânsito":
        return jsonify({
            "ok": False,
            "erro": "Essa movimentação já foi recebida ou cancelada.",
        }), 409

    foto = request.files.get("foto_material")

    if extensao_arquivo(foto) not in EXTENSOES_IMAGEM:
        return jsonify({
            "ok": False,
            "erro": "Tire uma foto válida do material recebido.",
        }), 400

    com_ressalva = request.form.get("com_ressalva", "nao") == "sim"
    observacao = request.form.get("observacao", "").strip()

    if com_ressalva and not observacao:
        return jsonify({
            "ok": False,
            "erro": "Descreva a divergência encontrada no recebimento.",
        }), 400

    latitude = parse_float(request.form.get("latitude"))
    longitude = parse_float(request.form.get("longitude"))
    precisao = parse_float(request.form.get("precisao_metros"))
    foto_path = None

    try:
        foto_path = salvar_foto_recebimento_material(
            foto,
            usuario.empresa_id,
        )
        movimentacao.status = (
            "Recebido com ressalva"
            if com_ressalva
            else "Recebido"
        )
        movimentacao.recebido_em = agora_local()
        movimentacao.recebido_por_id = usuario.id
        movimentacao.foto_recebimento = foto_path
        movimentacao.latitude_recebimento = latitude
        movimentacao.longitude_recebimento = longitude
        movimentacao.precisao_metros = precisao
        movimentacao.observacao_recebimento = observacao or None
        movimentacao.client_uuid_recebimento = client_uuid
        db.session.commit()
    except ValueError as erro_arquivo:
        db.session.rollback()
        remover_arquivo_mobile(foto_path)
        return jsonify({"ok": False, "erro": str(erro_arquivo)}), 400
    except Exception:
        db.session.rollback()
        remover_arquivo_mobile(foto_path)
        current_app.logger.exception("Falha ao receber material pelo app")
        return jsonify({
            "ok": False,
            "erro": "Não foi possível confirmar o recebimento.",
        }), 500

    return jsonify({
        "ok": True,
        "mensagem": "Material recebido e comprovante registrado.",
        "movimentacao": serializar_movimentacao_material(movimentacao),
    })


@mobile_api_bp.get("/diario/estado")
@token_obrigatorio
def estado_diario():
    usuario = g.mobile_user
    motorista, erro = motorista_do_usuario(usuario)

    if erro:
        return jsonify({
            "ok": False,
            "codigo": "vinculo_motorista",
            "erro": erro,
        }), 403

    return jsonify({
        "ok": True,
        **serializar_estado_diario(usuario, motorista),
    })


@mobile_api_bp.post("/diario/iniciar")
@token_obrigatorio
def iniciar_diario():
    usuario = g.mobile_user
    motorista, erro = motorista_do_usuario(usuario)

    if erro:
        return jsonify({"ok": False, "erro": erro}), 403

    veiculo = motorista.veiculo

    if veiculo is None:
        return jsonify({
            "ok": False,
            "erro": "Você não possui um veículo vinculado.",
        }), 409

    if motorista.status != "Ativo" or veiculo.status != "Ativo":
        return jsonify({
            "ok": False,
            "erro": "O motorista ou o veículo está inativo.",
        }), 409

    conflito_motorista = diario_aberto_motorista(usuario, motorista)

    if conflito_motorista:
        return jsonify({
            "ok": False,
            "erro": (
                "Você já possui um diário em andamento. "
                "Finalize-o antes de iniciar outro."
            ),
            "estado": serializar_estado_diario(usuario, motorista),
        }), 409

    conflito_veiculo = diario_aberto_veiculo(usuario, veiculo.id)

    if conflito_veiculo:
        return jsonify({
            "ok": False,
            "erro": "O veículo vinculado já possui um diário em andamento.",
        }), 409

    data_registro = converter_data_diario(request.form.get("data"))
    hora_saida = converter_hora_diario(request.form.get("hora_saida"))
    km_inicial = converter_inteiro_diario(request.form.get("km_inicial"))
    origem = request.form.get("origem", "").strip()
    destino = request.form.get("destino", "").strip()
    finalidade = request.form.get("finalidade", "").strip()
    ocorrencias = request.form.get("ocorrencias", "").strip()
    obra, erro_obra = obter_obra_mobile(usuario, request.form.get("obra_id"))

    if data_registro is None:
        return jsonify({"ok": False, "erro": "Informe uma data válida."}), 400

    if hora_saida is None:
        return jsonify({"ok": False, "erro": "Informe a hora de saída."}), 400

    if km_inicial is None or km_inicial < 0:
        return jsonify({"ok": False, "erro": "Informe um KM inicial válido."}), 400

    if not origem or not destino:
        return jsonify({
            "ok": False,
            "erro": "Informe a origem e o destino do deslocamento.",
        }), 400

    if erro_obra:
        return jsonify({"ok": False, "erro": erro_obra}), 400

    houve_abastecimento = (
        request.form.get("houve_abastecimento", "nao").lower() == "sim"
    )
    posto = request.form.get("posto_abastecimento", "").strip()
    litros = converter_decimal_diario(
        request.form.get("litros_abastecimento")
    )
    valor_litro = converter_decimal_diario(
        request.form.get("valor_litro_abastecimento")
    )
    numero_nota = request.form.get("numero_nota_abastecimento", "").strip()
    tanque_cheio = (
        request.form.get("tanque_cheio_abastecimento") == "sim"
    )
    foto_odometro_arquivo = request.files.get("foto_odometro")
    cupom_fiscal_arquivo = request.files.get("cupom_fiscal")
    transporta_material = (
        request.form.get("transporta_material", "nao").lower() == "sim"
    )
    material = request.form.get("material", "").strip()
    numero_movimentacao = request.form.get(
        "numero_movimentacao",
        "",
    ).strip()
    quantidade_material = converter_decimal_diario(
        request.form.get("quantidade_material")
    )
    unidade_material = request.form.get("unidade_material", "").strip()
    observacao_material = request.form.get(
        "observacao_material",
        "",
    ).strip()

    if houve_abastecimento:
        if not (veiculo.combustivel or "").strip():
            return jsonify({
                "ok": False,
                "erro": "O veículo não possui combustível cadastrado.",
            }), 400

        if not posto:
            return jsonify({
                "ok": False,
                "erro": "Informe o posto ou fornecedor.",
            }), 400

        if litros is None or litros <= 0:
            return jsonify({
                "ok": False,
                "erro": "A quantidade de litros deve ser maior que zero.",
            }), 400

        if valor_litro is None or valor_litro <= 0:
            return jsonify({
                "ok": False,
                "erro": "O valor por litro deve ser maior que zero.",
            }), 400

        if extensao_arquivo(foto_odometro_arquivo) not in EXTENSOES_IMAGEM:
            return jsonify({
                "ok": False,
                "erro": "Inclua uma foto válida do odômetro.",
            }), 400

        if extensao_arquivo(cupom_fiscal_arquivo) not in EXTENSOES_COMPROVANTE:
            return jsonify({
                "ok": False,
                "erro": "Inclua uma foto válida do cupom fiscal.",
            }), 400

    if transporta_material:
        if not material:
            return jsonify({
                "ok": False,
                "erro": "Informe o material transportado.",
            }), 400

        if not numero_movimentacao:
            return jsonify({
                "ok": False,
                "erro": "Informe o número da movimentação.",
            }), 400

        if quantidade_material is not None and quantidade_material <= 0:
            return jsonify({
                "ok": False,
                "erro": "A quantidade do material deve ser maior que zero.",
            }), 400

        if quantidade_material is not None and not unidade_material:
            return jsonify({
                "ok": False,
                "erro": "Informe a unidade do material.",
            }), 400

        if unidade_material and quantidade_material is None:
            return jsonify({
                "ok": False,
                "erro": "Informe a quantidade ou deixe a unidade vazia.",
            }), 400

    diario = DiarioBordo(
        empresa_id=usuario.empresa_id,
        veiculo_id=veiculo.id,
        motorista_id=motorista.id,
        obra_id=obra.id if obra else None,
        data=data_registro,
        hora_saida=hora_saida,
        hora_retorno=None,
        km_inicial=km_inicial,
        km_final=None,
        origem=origem,
        destino=destino,
        finalidade=finalidade or None,
        ocorrencias=ocorrencias or None,
        status="Em andamento",
    )

    arquivos_salvos = []

    try:
        db.session.add(diario)
        db.session.flush()

        if transporta_material:
            movimentacao = MovimentacaoMaterial(
                empresa_id=usuario.empresa_id,
                diario_bordo_id=diario.id,
                material=material,
                numero_movimentacao=numero_movimentacao,
                quantidade=quantidade_material,
                unidade=unidade_material or None,
                observacao_carga=observacao_material or None,
                status="Em trânsito",
            )
            db.session.add(movimentacao)

        if houve_abastecimento:
            foto_odometro = salvar_arquivo_abastecimento_mobile(
                foto_odometro_arquivo,
                usuario.empresa_id,
                "odometro",
                EXTENSOES_IMAGEM,
            )
            arquivos_salvos.append(foto_odometro)

            cupom_fiscal = salvar_arquivo_abastecimento_mobile(
                cupom_fiscal_arquivo,
                usuario.empresa_id,
                "cupom",
                EXTENSOES_COMPROVANTE,
            )
            arquivos_salvos.append(cupom_fiscal)

            abastecimento = Abastecimento(
                empresa_id=usuario.empresa_id,
                usuario_id=usuario.id,
                veiculo_id=veiculo.id,
                motorista_id=motorista.id,
                obra_id=obra.id if obra else None,
                diario_bordo_id=diario.id,
                data=data_registro,
                hora=hora_saida,
                posto=posto,
                combustivel=veiculo.combustivel,
                litros=litros,
                valor_litro=valor_litro,
                valor_total=calcular_total_abastecimento(litros, valor_litro),
                km=km_inicial,
                tanque_cheio=tanque_cheio,
                numero_nota=numero_nota or None,
                comprovante=cupom_fiscal,
                foto_odometro=foto_odometro,
                observacoes=(
                    f"Registrado pelo aplicativo na abertura do diário #{diario.id}."
                ),
            )
            db.session.add(abastecimento)

        if km_inicial > veiculo.km_atual:
            veiculo.km_atual = km_inicial

        db.session.commit()
    except ValueError as erro_arquivo:
        db.session.rollback()

        for caminho in arquivos_salvos:
            remover_arquivo_mobile(caminho)

        return jsonify({"ok": False, "erro": str(erro_arquivo)}), 400
    except Exception:
        db.session.rollback()

        for caminho in arquivos_salvos:
            remover_arquivo_mobile(caminho)

        current_app.logger.exception("Falha ao iniciar diário pelo aplicativo")
        return jsonify({
            "ok": False,
            "erro": "Não foi possível iniciar o diário. Tente novamente.",
        }), 500

    return jsonify({
        "ok": True,
        "mensagem": (
            "Diário iniciado e movimentação enviada aos apontadores."
            if transporta_material
            else (
                "Diário e abastecimento registrados com sucesso."
                if houve_abastecimento
                else "Diário iniciado com sucesso."
            )
        ),
        "estado": serializar_estado_diario(usuario, motorista),
    }), 201


@mobile_api_bp.post("/diario/<int:diario_id>/finalizar")
@token_obrigatorio
def finalizar_diario_mobile(diario_id):
    usuario = g.mobile_user
    motorista, erro = motorista_do_usuario(usuario)

    if erro:
        return jsonify({"ok": False, "erro": erro}), 403

    diario = DiarioBordo.query.filter_by(
        id=diario_id,
        empresa_id=usuario.empresa_id,
        motorista_id=motorista.id,
    ).first()

    if diario is None:
        return jsonify({
            "ok": False,
            "erro": "Diário de bordo não encontrado.",
        }), 404

    if diario.status == "Concluído":
        return jsonify({
            "ok": True,
            "mensagem": "Esse diário já estava finalizado.",
            "estado": serializar_estado_diario(usuario, motorista),
        })

    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        return jsonify({
            "ok": False,
            "erro": "Envie a hora de chegada e o KM final.",
        }), 400

    if not str(dados.get("hora_chegada", "")).strip():
        return jsonify({
            "ok": False,
            "erro": "Informe a hora de chegada.",
        }), 400

    hora_chegada = converter_hora_diario(dados.get("hora_chegada"))
    km_final = converter_inteiro_diario(dados.get("km_final"))

    if hora_chegada is None:
        return jsonify({
            "ok": False,
            "erro": "Informe uma hora de chegada válida.",
        }), 400

    if km_final is None or km_final < diario.km_inicial:
        return jsonify({
            "ok": False,
            "erro": "O KM final deve ser igual ou maior que o KM inicial.",
        }), 400

    try:
        diario.hora_retorno = hora_chegada
        diario.km_final = km_final
        diario.status = "Concluído"

        if km_final > diario.veiculo.km_atual:
            diario.veiculo.km_atual = km_final

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao finalizar diário pelo aplicativo")
        return jsonify({
            "ok": False,
            "erro": "Não foi possível finalizar o diário. Tente novamente.",
        }), 500

    return jsonify({
        "ok": True,
        "mensagem": "Diário finalizado com sucesso.",
        "estado": serializar_estado_diario(usuario, motorista),
    })
