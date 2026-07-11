import os
import re
from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from database.configuracao_empresa import ConfiguracaoEmpresa
from database.models import Empresa, Veiculo
from extensions import db


configuracoes_bp = Blueprint(
    "configuracoes",
    __name__,
)


EXTENSOES_LOGO_PERMITIDAS = {
    "jpg",
    "jpeg",
    "png",
    "webp",
}

TAMANHO_MAXIMO_LOGO = 2 * 1024 * 1024


def usuario_e_administrador():
    perfil = (
        current_user.perfil
        or ""
    ).strip().lower()

    return perfil == "administrador"


def somente_digitos(valor):
    return re.sub(
        r"\D",
        "",
        valor or "",
    )


def formatar_cnpj(valor):
    digitos = somente_digitos(valor)

    if len(digitos) != 14:
        return valor.strip()

    return (
        f"{digitos[0:2]}."
        f"{digitos[2:5]}."
        f"{digitos[5:8]}/"
        f"{digitos[8:12]}-"
        f"{digitos[12:14]}"
    )


def email_valido(valor):
    if not valor:
        return True

    padrao = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

    return re.match(
        padrao,
        valor,
    ) is not None


def extensao_permitida(nome_arquivo):
    if "." not in nome_arquivo:
        return False

    extensao = (
        nome_arquivo
        .rsplit(".", 1)[1]
        .lower()
    )

    return extensao in EXTENSOES_LOGO_PERMITIDAS


def tamanho_arquivo(arquivo):
    posicao_atual = arquivo.stream.tell()

    arquivo.stream.seek(
        0,
        os.SEEK_END,
    )

    tamanho = arquivo.stream.tell()

    arquivo.stream.seek(
        posicao_atual,
        os.SEEK_SET,
    )

    return tamanho


def salvar_logo(
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
            "A logo deve estar em JPG, PNG ou WEBP."
        )

    if tamanho_arquivo(arquivo) > TAMANHO_MAXIMO_LOGO:
        raise ValueError(
            "A logo deve ter no mÃ¡ximo 2 MB."
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
        "empresas",
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


def remover_arquivo(caminho_relativo):
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


def obter_ou_criar_configuracao(empresa):
    configuracao = (
        ConfiguracaoEmpresa.query
        .filter_by(
            empresa_id=empresa.id,
        )
        .first()
    )

    if configuracao is None:
        configuracao = ConfiguracaoEmpresa(
            empresa_id=empresa.id,
            exibir_logo_relatorios=True,
        )

    return configuracao


def dados_da_tela(
    empresa,
    configuracao,
):
    return {
        "razao_social": empresa.razao_social or "",
        "nome_fantasia": empresa.nome_fantasia or "",
        "cnpj": empresa.cnpj or "",
        "email": configuracao.email or "",
        "telefone": configuracao.telefone or "",
        "whatsapp": configuracao.whatsapp or "",
        "cep": configuracao.cep or "",
        "logradouro": configuracao.logradouro or "",
        "numero": configuracao.numero or "",
        "complemento": configuracao.complemento or "",
        "bairro": configuracao.bairro or "",
        "cidade": configuracao.cidade or "",
        "estado": configuracao.estado or "",
        "responsavel": configuracao.responsavel or "",
        "rodape_relatorios": (
            configuracao.rodape_relatorios
            or ""
        ),
        "exibir_logo_relatorios": (
            configuracao.exibir_logo_relatorios
        ),
    }


def dados_do_formulario():
    return {
        "razao_social": (
            request.form
            .get("razao_social", "")
            .strip()
        ),
        "nome_fantasia": (
            request.form
            .get("nome_fantasia", "")
            .strip()
        ),
        "cnpj": (
            request.form
            .get("cnpj", "")
            .strip()
        ),
        "email": (
            request.form
            .get("email", "")
            .strip()
            .lower()
        ),
        "telefone": (
            request.form
            .get("telefone", "")
            .strip()
        ),
        "whatsapp": (
            request.form
            .get("whatsapp", "")
            .strip()
        ),
        "cep": (
            request.form
            .get("cep", "")
            .strip()
        ),
        "logradouro": (
            request.form
            .get("logradouro", "")
            .strip()
        ),
        "numero": (
            request.form
            .get("numero", "")
            .strip()
        ),
        "complemento": (
            request.form
            .get("complemento", "")
            .strip()
        ),
        "bairro": (
            request.form
            .get("bairro", "")
            .strip()
        ),
        "cidade": (
            request.form
            .get("cidade", "")
            .strip()
        ),
        "estado": (
            request.form
            .get("estado", "")
            .strip()
            .upper()
        ),
        "responsavel": (
            request.form
            .get("responsavel", "")
            .strip()
        ),
        "rodape_relatorios": (
            request.form
            .get("rodape_relatorios", "")
            .strip()
        ),
        "exibir_logo_relatorios": (
            request.form.get(
                "exibir_logo_relatorios"
            )
            == "on"
        ),
    }


def validar_dados(
    dados,
    empresa_id,
):
    erros = []

    if not dados["razao_social"]:
        erros.append(
            "Informe a razÃ£o social da empresa."
        )

    cnpj_digitos = somente_digitos(
        dados["cnpj"]
    )

    if dados["cnpj"] and len(cnpj_digitos) != 14:
        erros.append(
            "O CNPJ deve possuir 14 nÃºmeros."
        )

    if len(cnpj_digitos) == 14:
        cnpj_formatado = formatar_cnpj(
            cnpj_digitos
        )

        empresa_existente = (
            Empresa.query
            .filter(
                Empresa.cnpj == cnpj_formatado,
                Empresa.id != empresa_id,
            )
            .first()
        )

        if empresa_existente:
            erros.append(
                "Este CNPJ jÃ¡ estÃ¡ vinculado a outra empresa."
            )

    if not email_valido(dados["email"]):
        erros.append(
            "Informe um endereÃ§o de e-mail vÃ¡lido."
        )

    if (
        dados["estado"]
        and len(dados["estado"]) != 2
    ):
        erros.append(
            "O estado deve ser informado com duas letras."
        )

    cep_digitos = somente_digitos(
        dados["cep"]
    )

    if dados["cep"] and len(cep_digitos) != 8:
        erros.append(
            "O CEP deve possuir 8 nÃºmeros."
        )

    return erros


def renderizar_pagina(
    empresa,
    configuracao,
    dados,
    erros=None,
):
    total_veiculos = (
        Veiculo.query
        .filter_by(
            empresa_id=empresa.id,
        )
        .count()
    )

    plano = empresa.plano

    return render_template(
        "configuracoes.html",
        empresa=empresa,
        configuracao=configuracao,
        dados=dados,
        erros=erros or [],
        plano=plano,
        total_veiculos=total_veiculos,
    )


@configuracoes_bp.route(
    "/configuracoes",
    methods=["GET", "POST"],
)
@login_required
def configuracoes_empresa():
    if not usuario_e_administrador():
        flash(
            "Somente administradores podem alterar "
            "as configuraÃ§Ãµes da empresa.",
            "warning",
        )

        return redirect(
            url_for("dashboard")
        )

    empresa = current_user.empresa

    configuracao = obter_ou_criar_configuracao(
        empresa
    )

    if request.method == "GET":
        return renderizar_pagina(
            empresa=empresa,
            configuracao=configuracao,
            dados=dados_da_tela(
                empresa,
                configuracao,
            ),
        )

    dados = dados_do_formulario()

    erros = validar_dados(
        dados,
        empresa.id,
    )

    arquivo_logo = request.files.get(
        "logo"
    )

    nova_logo = None

    if arquivo_logo and arquivo_logo.filename:
        try:
            nova_logo = salvar_logo(
                arquivo_logo,
                empresa.id,
            )
        except ValueError as erro_logo:
            erros.append(
                str(erro_logo)
            )

    if erros:
        if nova_logo:
            remover_arquivo(
                nova_logo
            )

        return renderizar_pagina(
            empresa=empresa,
            configuracao=configuracao,
            dados=dados,
            erros=erros,
        )

    logo_anterior = configuracao.logo

    remover_logo = (
        request.form.get("remover_logo")
        == "1"
    )

    empresa.razao_social = (
        dados["razao_social"]
    )

    empresa.nome_fantasia = (
        dados["nome_fantasia"]
        or None
    )

    empresa.cnpj = (
        formatar_cnpj(dados["cnpj"])
        if dados["cnpj"]
        else None
    )

    configuracao.email = (
        dados["email"]
        or None
    )

    configuracao.telefone = (
        dados["telefone"]
        or None
    )

    configuracao.whatsapp = (
        dados["whatsapp"]
        or None
    )

    configuracao.cep = (
        dados["cep"]
        or None
    )

    configuracao.logradouro = (
        dados["logradouro"]
        or None
    )

    configuracao.numero = (
        dados["numero"]
        or None
    )

    configuracao.complemento = (
        dados["complemento"]
        or None
    )

    configuracao.bairro = (
        dados["bairro"]
        or None
    )

    configuracao.cidade = (
        dados["cidade"]
        or None
    )

    configuracao.estado = (
        dados["estado"]
        or None
    )

    configuracao.responsavel = (
        dados["responsavel"]
        or None
    )

    configuracao.rodape_relatorios = (
        dados["rodape_relatorios"]
        or None
    )

    configuracao.exibir_logo_relatorios = (
        dados["exibir_logo_relatorios"]
    )

    if nova_logo:
        configuracao.logo = nova_logo

    elif remover_logo:
        configuracao.logo = None

    db.session.add(configuracao)

    try:
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()

        if nova_logo:
            remover_arquivo(
                nova_logo
            )

        flash(
            "NÃ£o foi possÃ­vel salvar as configuraÃ§Ãµes. "
            "Tente novamente.",
            "danger",
        )

        return renderizar_pagina(
            empresa=empresa,
            configuracao=configuracao,
            dados=dados,
        )

    if (
        logo_anterior
        and (
            nova_logo
            or remover_logo
        )
        and logo_anterior
        != configuracao.logo
    ):
        remover_arquivo(
            logo_anterior
        )

    flash(
        "Configurações da empresa atualizadas com sucesso.",
        "success",
    )

    return redirect(
        url_for(
            "configuracoes.configuracoes_empresa"
        )
    )
