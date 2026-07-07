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

conn.commit()
conn.close()

print("Banco de dados criado com sucesso.")