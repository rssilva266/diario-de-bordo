import sqlite3
from flask import Blueprint, render_template, request, redirect

veiculos_bp = Blueprint("veiculos", __name__)

def conectar():
    return sqlite3.connect("database/banco.db")

@veiculos_bp.route("/veiculos")
def listar_veiculos():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, placa, modelo, ano, combustivel, km_atual, media_esperada
        FROM veiculos
    """)
    veiculos = cursor.fetchall()

    conn.close()

    return render_template("veiculos.html", veiculos=veiculos)


@veiculos_bp.route("/veiculos/novo", methods=["POST"])
def novo_veiculo():
    placa = request.form["placa"]
    modelo = request.form["modelo"]
    ano = request.form["ano"]
    combustivel = request.form["combustivel"]
    km_atual = request.form["km_atual"]
    media_esperada = request.form["media_esperada"]

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO veiculos 
        (placa, modelo, ano, combustivel, km_atual, media_esperada)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (placa, modelo, ano, combustivel, km_atual, media_esperada))

    conn.commit()
    conn.close()

    return redirect("/veiculos")