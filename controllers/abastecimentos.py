import os
import sqlite3
from flask import Blueprint, render_template, request, redirect
from werkzeug.utils import secure_filename

abastecimentos_bp = Blueprint("abastecimentos", __name__)

UPLOAD_BASE = "static/uploads"

def conectar():
    return sqlite3.connect("database/banco.db")

def salvar_arquivo(arquivo, pasta):
    if not arquivo or arquivo.filename == "":
        return None

    os.makedirs(pasta, exist_ok=True)

    nome_seguro = secure_filename(arquivo.filename)
    caminho = os.path.join(pasta, nome_seguro)

    arquivo.save(caminho)

    return caminho


@abastecimentos_bp.route("/abastecimentos")
def listar_abastecimentos():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            a.id,
            a.data,
            v.placa,
            v.modelo,
            a.motorista,
            a.valor_total,
            a.litros,
            a.odometro
        FROM abastecimentos a
        JOIN veiculos v ON v.id = a.veiculo_id
        WHERE a.ativo = 1
        ORDER BY a.data DESC, a.id DESC
    """)

    abastecimentos = cursor.fetchall()
    conn.close()

    return render_template("abastecimentos.html", abastecimentos=abastecimentos)


@abastecimentos_bp.route("/abastecimentos/novo", methods=["GET", "POST"])
def novo_abastecimento():
    conn = conectar()
    cursor = conn.cursor()

    if request.method == "POST":
        data = request.form["data"]
        veiculo_id = request.form["veiculo_id"]
        motorista = request.form["motorista"]
        obra = request.form["obra"]
        combustivel = request.form["combustivel"]
        valor_total = float(request.form["valor_total"])
        litros = float(request.form["litros"])
        odometro = int(request.form["odometro"])
        observacao = request.form["observacao"]

        valor_litro = valor_total / litros if litros > 0 else 0

        cupom_foto = salvar_arquivo(request.files.get("cupom_foto"), f"{UPLOAD_BASE}/cupons")
        odometro_foto = salvar_arquivo(request.files.get("odometro_foto"), f"{UPLOAD_BASE}/odometros")
        placa_foto = salvar_arquivo(request.files.get("placa_foto"), f"{UPLOAD_BASE}/placas")

        cursor.execute("""
            INSERT INTO abastecimentos (
                data, veiculo_id, motorista, obra, combustivel,
                valor_total, litros, valor_litro, odometro,
                cupom_foto, odometro_foto, placa_foto,
                observacao
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data, veiculo_id, motorista, obra, combustivel,
            valor_total, litros, valor_litro, odometro,
            cupom_foto, odometro_foto, placa_foto,
            observacao
        ))

        conn.commit()
        conn.close()

        return redirect("/abastecimentos")

    cursor.execute("SELECT id, placa, modelo FROM veiculos WHERE ativo = 1 OR ativo IS NULL")
    veiculos = cursor.fetchall()
    conn.close()

    return render_template("abastecimentos_novo.html", veiculos=veiculos)