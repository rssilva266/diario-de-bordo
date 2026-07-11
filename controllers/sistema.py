import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from extensions import db


sistema_bp = Blueprint("sistema", __name__)


def administrador_required(funcao):
    @wraps(funcao)
    @login_required
    def decorada(*args, **kwargs):
        perfil = (current_user.perfil or "").strip().lower()
        if perfil != "administrador":
            flash("Acesso permitido somente para administradores.", "warning")
            return redirect(url_for("dashboard"))
        return funcao(*args, **kwargs)

    return decorada


def pasta_projeto():
    return Path(current_app.root_path).resolve()


def pasta_backups():
    pasta = pasta_projeto() / "backups"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def caminho_banco():
    return pasta_projeto() / "database" / "banco.db"


def tamanho_formatado(tamanho):
    valor = float(tamanho)
    for unidade in ("B", "KB", "MB", "GB", "TB"):
        if valor < 1024 or unidade == "TB":
            return f"{valor:.1f} {unidade}"
        valor /= 1024
    return f"{valor:.1f} TB"


def criar_backup(sufixo="manual"):
    agora = datetime.now()
    nome = f"msm_suite_{agora:%Y%m%d_%H%M%S}_{sufixo}.zip"
    destino = pasta_backups() / nome
    raiz = pasta_projeto()
    banco = caminho_banco()

    manifesto = {
        "produto": "MSM Suite",
        "criado_em": agora.isoformat(timespec="seconds"),
        "tipo": sufixo,
        "usuario": getattr(current_user, "usuario", "sistema"),
        "empresa_id": getattr(current_user, "empresa_id", None),
        "conteudo": ["database/banco.db", "static/uploads"],
    }

    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as arquivo_zip:
        arquivo_zip.writestr(
            "backup_manifest.json",
            json.dumps(manifesto, ensure_ascii=False, indent=2),
        )

        if banco.exists():
            arquivo_zip.write(banco, "database/banco.db")

        uploads = raiz / "static" / "uploads"
        if uploads.exists():
            for arquivo in uploads.rglob("*"):
                if arquivo.is_file():
                    arquivo_zip.write(
                        arquivo,
                        arquivo.relative_to(raiz).as_posix(),
                    )

    return destino


def listar_backups():
    itens = []
    for caminho in sorted(
        pasta_backups().glob("msm_suite_*.zip"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        stat = caminho.stat()
        itens.append(
            {
                "nome": caminho.name,
                "tamanho": tamanho_formatado(stat.st_size),
                "criado_em": datetime.fromtimestamp(stat.st_mtime),
            }
        )
    return itens


def backup_por_nome(nome):
    nome_seguro = Path(nome).name
    caminho = (pasta_backups() / nome_seguro).resolve()
    try:
        caminho.relative_to(pasta_backups().resolve())
    except ValueError:
        return None
    if not caminho.exists() or caminho.suffix.lower() != ".zip":
        return None
    return caminho


def executar_git(*argumentos):
    resultado = subprocess.run(
        ["git", *argumentos],
        cwd=pasta_projeto(),
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    saida = (resultado.stdout or "").strip()
    erro = (resultado.stderr or "").strip()
    return resultado.returncode, saida, erro


def estado_git(atualizar=False):
    dados = {
        "disponivel": False,
        "branch": "Não identificado",
        "commit": "Não identificado",
        "remoto": "Não configurado",
        "limpo": False,
        "atrasado": None,
        "mensagem": None,
    }

    try:
        codigo, branch, erro = executar_git("branch", "--show-current")
        if codigo != 0:
            dados["mensagem"] = erro or "Git não disponível neste ambiente."
            return dados

        dados["disponivel"] = True
        dados["branch"] = branch or "detached"

        _, commit, _ = executar_git("rev-parse", "--short", "HEAD")
        dados["commit"] = commit or "Não identificado"

        _, remoto, _ = executar_git("remote", "get-url", "origin")
        dados["remoto"] = remoto or "Não configurado"

        _, status, _ = executar_git("status", "--porcelain")
        dados["limpo"] = not bool(status)

        if atualizar and remoto:
            executar_git("fetch", "--prune", "origin")

        codigo, atrasado, _ = executar_git(
            "rev-list", "--count", "HEAD..@{upstream}"
        )
        if codigo == 0:
            dados["atrasado"] = int(atrasado or 0)
    except (OSError, subprocess.SubprocessError, ValueError) as erro:
        dados["mensagem"] = str(erro)

    return dados


@sistema_bp.route("/administracao/backup")
@administrador_required
def backups():
    return render_template(
        "administracao/backup.html",
        backups=listar_backups(),
    )


@sistema_bp.route("/administracao/backup/criar", methods=["POST"])
@administrador_required
def criar_backup_manual():
    try:
        caminho = criar_backup("manual")
        flash(f"Backup criado com sucesso: {caminho.name}", "success")
    except (OSError, zipfile.BadZipFile) as erro:
        current_app.logger.exception("Falha ao criar backup")
        flash(f"Não foi possível criar o backup: {erro}", "danger")
    return redirect(url_for("sistema.backups"))


@sistema_bp.route("/administracao/backup/baixar/<nome>")
@administrador_required
def baixar_backup(nome):
    caminho = backup_por_nome(nome)
    if caminho is None:
        flash("Backup não encontrado.", "warning")
        return redirect(url_for("sistema.backups"))
    return send_file(caminho, as_attachment=True, download_name=caminho.name)


@sistema_bp.route("/administracao/backup/excluir/<nome>", methods=["POST"])
@administrador_required
def excluir_backup(nome):
    caminho = backup_por_nome(nome)
    if caminho is None:
        flash("Backup não encontrado.", "warning")
    else:
        caminho.unlink()
        flash("Backup excluído.", "success")
    return redirect(url_for("sistema.backups"))


@sistema_bp.route("/administracao/backup/restaurar/<nome>", methods=["POST"])
@administrador_required
def restaurar_backup(nome):
    confirmacao = request.form.get("confirmacao", "").strip().upper()
    if confirmacao != "RESTAURAR":
        flash("Digite RESTAURAR para confirmar a operação.", "warning")
        return redirect(url_for("sistema.backups"))

    caminho = backup_por_nome(nome)
    if caminho is None:
        flash("Backup não encontrado.", "warning")
        return redirect(url_for("sistema.backups"))

    seguranca = None
    temporaria = pasta_backups() / f"restore_{datetime.now():%Y%m%d_%H%M%S}"
    temporaria.mkdir(parents=True, exist_ok=True)

    try:
        seguranca = criar_backup("antes_restauracao")

        with zipfile.ZipFile(caminho, "r") as arquivo_zip:
            nomes = set(arquivo_zip.namelist())
            if "backup_manifest.json" not in nomes or "database/banco.db" not in nomes:
                raise ValueError("O arquivo não é um backup válido do MSM Suite.")

            for membro in arquivo_zip.infolist():
                alvo = (temporaria / membro.filename).resolve()
                alvo.relative_to(temporaria.resolve())
            arquivo_zip.extractall(temporaria)

        db.session.remove()
        db.engine.dispose()

        banco_origem = temporaria / "database" / "banco.db"
        shutil.copy2(banco_origem, caminho_banco())

        uploads_origem = temporaria / "static" / "uploads"
        uploads_destino = pasta_projeto() / "static" / "uploads"
        if uploads_origem.exists():
            if uploads_destino.exists():
                shutil.rmtree(uploads_destino)
            shutil.copytree(uploads_origem, uploads_destino)

        flash(
            "Backup restaurado. Reinicie o serviço do sistema antes de continuar.",
            "success",
        )
    except (OSError, ValueError, zipfile.BadZipFile) as erro:
        current_app.logger.exception("Falha ao restaurar backup")
        mensagem = f"Falha na restauração: {erro}"
        if seguranca:
            mensagem += f" Backup de segurança: {seguranca.name}."
        flash(mensagem, "danger")
    finally:
        shutil.rmtree(temporaria, ignore_errors=True)

    return redirect(url_for("sistema.backups"))


@sistema_bp.route("/administracao/atualizacoes")
@administrador_required
def atualizacoes():
    return render_template(
        "administracao/atualizacoes.html",
        git=estado_git(atualizar=False),
    )


@sistema_bp.route("/administracao/atualizacoes/verificar", methods=["POST"])
@administrador_required
def verificar_atualizacoes():
    git = estado_git(atualizar=True)
    if not git["disponivel"]:
        flash(git["mensagem"] or "Git não está disponível.", "danger")
    elif git["atrasado"] is None:
        flash("Não foi possível comparar com a branch remota.", "warning")
    elif git["atrasado"] > 0:
        flash(f"Há {git['atrasado']} atualização(ões) disponível(is).", "info")
    else:
        flash("O sistema já está atualizado.", "success")
    return render_template("administracao/atualizacoes.html", git=git)


@sistema_bp.route("/administracao/atualizacoes/aplicar", methods=["POST"])
@administrador_required
def aplicar_atualizacao():
    confirmacao = request.form.get("confirmacao", "").strip().upper()
    if confirmacao != "ATUALIZAR":
        flash("Digite ATUALIZAR para confirmar.", "warning")
        return redirect(url_for("sistema.atualizacoes"))

    git = estado_git(atualizar=True)
    if not git["disponivel"]:
        flash("Git não está disponível neste ambiente.", "danger")
        return redirect(url_for("sistema.atualizacoes"))
    if not git["limpo"]:
        flash(
            "Existem alterações locais não salvas. Faça commit ou descarte-as antes de atualizar.",
            "warning",
        )
        return redirect(url_for("sistema.atualizacoes"))

    try:
        backup = criar_backup("antes_atualizacao")
        codigo, saida, erro = executar_git("pull", "--ff-only")
        if codigo != 0:
            raise RuntimeError(erro or saida or "Falha no git pull.")

        migracao = subprocess.run(
            [sys.executable, "-m", "flask", "--app", "app", "db", "upgrade"],
            cwd=pasta_projeto(),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if migracao.returncode != 0:
            raise RuntimeError(
                migracao.stderr.strip()
                or migracao.stdout.strip()
                or "Falha ao atualizar o banco."
            )

        flash(
            f"Atualização aplicada. Backup automático: {backup.name}. Reinicie o serviço.",
            "success",
        )
    except (OSError, RuntimeError, subprocess.SubprocessError) as erro:
        current_app.logger.exception("Falha ao aplicar atualização")
        flash(f"Atualização não aplicada: {erro}", "danger")

    return redirect(url_for("sistema.atualizacoes"))
