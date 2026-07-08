import sqlite3
import os

os.makedirs("database", exist_ok=True)

conn = sqlite3.connect("database/banco.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS veiculos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    placa TEXT NOT NULL,
    modelo TEXT NOT NULL,
    ano INTEGER,
    combustivel TEXT,
    km_atual INTEGER DEFAULT 0
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS abastecimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    veiculo_id INTEGER NOT NULL,
    motorista TEXT NOT NULL,
    obra TEXT,
    combustivel TEXT,
    valor_total REAL NOT NULL,
    litros REAL NOT NULL,
    valor_litro REAL,
    odometro INTEGER NOT NULL,
    cupom_foto TEXT,
    odometro_foto TEXT,
    placa_foto TEXT,
    observacao TEXT,
    ativo INTEGER DEFAULT 1,
    FOREIGN KEY (veiculo_id) REFERENCES veiculos(id)
)
""")
conn.commit()
conn.close()

print("Banco de dados criado com sucesso.")