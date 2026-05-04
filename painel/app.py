import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv

load_dotenv("config.env")

from db import init_db, listar_ofertas
from painel.auth import login_required, verificar_senha
from painel.state import ler_estado, pausar, forcar_rodada

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("FLASK_SECRET", "mude-isso-em-producao")

init_db()


@app.route("/login", methods=["GET", "POST"])
def login():
    erro = None
    if request.method == "POST":
        if verificar_senha(request.form.get("senha", "")):
            session["autenticado"] = True
            return redirect(url_for("dashboard"))
        erro = "Senha incorreta"
    return render_template("login.html", erro=erro)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    return render_template("index.html")


@app.route("/api/status")
@login_required
def api_status():
    return jsonify(ler_estado())


@app.route("/api/ofertas")
@login_required
def api_ofertas():
    return jsonify(listar_ofertas(100))


@app.route("/api/config", methods=["GET", "POST"])
@login_required
def api_config():
    config_file = "config.env"
    if request.method == "GET":
        cfg = {}
        with open(config_file) as f:
            for linha in f:
                linha = linha.strip()
                if "=" in linha and not linha.startswith("#"):
                    k, v = linha.split("=", 1)
                    cfg[k.strip()] = v.strip()
        campos_publicos = ["MIN_DESCONTO", "MAX_OFERTAS_POR_RODADA",
                           "INTERVALO_ENTRE_POSTS", "RODAR_A_CADA_MINUTOS",
                           "HORA_INICIO", "HORA_FIM", "WHATSAPP_GROUP_NAME"]
        return jsonify({k: cfg.get(k, "") for k in campos_publicos})
    data = request.json or {}
    linhas = []
    with open(config_file) as f:
        linhas = f.readlines()
    for k, v in data.items():
        found = False
        for i, linha in enumerate(linhas):
            if linha.strip().startswith(k + "="):
                linhas[i] = f"{k}={v}\n"
                found = True
                break
        if not found:
            linhas.append(f"{k}={v}\n")
    with open(config_file, "w") as f:
        f.writelines(linhas)
    return jsonify({"ok": True})


@app.route("/api/categorias", methods=["GET", "POST"])
@login_required
def api_categorias():
    cat_file = "categorias.txt"
    if request.method == "GET":
        with open(cat_file, encoding="utf-8") as f:
            cats = [l.strip() for l in f if l.strip()]
        return jsonify(cats)
    data = request.json or {}
    cats = data.get("categorias", [])
    with open(cat_file, "w", encoding="utf-8") as f:
        f.write("\n".join(cats) + "\n")
    return jsonify({"ok": True})


@app.route("/api/pausar", methods=["POST"])
@login_required
def api_pausar():
    data = request.json or {}
    pausar(data.get("pausado", False))
    return jsonify({"ok": True})


@app.route("/api/forcar-rodada", methods=["POST"])
@login_required
def api_forcar_rodada():
    forcar_rodada()
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
