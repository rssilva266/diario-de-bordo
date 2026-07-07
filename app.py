from flask import Flask, render_template

from controllers.veiculos import veiculos_bp

app = Flask(__name__)

app.register_blueprint(veiculos_bp)

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/motoristas")
def motoristas():
    return render_template("motoristas.html")

@app.route("/obras")
def obras():
    return render_template("obras.html")

@app.route("/abastecimentos")
def abastecimentos():
    return render_template("abastecimentos.html")

@app.route("/diario")
def diario():
    return render_template("diario.html")

@app.route("/relatorios")
def relatorios():
    return render_template("relatorios.html")

@app.route("/configuracoes")
def configuracoes():
    return render_template("configuracoes.html")

if __name__ == "__main__":
    app.run(debug=True)