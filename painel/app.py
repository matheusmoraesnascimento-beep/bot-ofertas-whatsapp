import os
import sys
import threading
import base64
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
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


# --- WhatsApp Auth ---
_wa_state = {"status": "idle", "qr_png": None}  # idle | waiting_qr | qr_ready | logged_in | error


def _run_wa_auth():
    import time
    SESSION_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".whatsapp_session")
    try:
        from playwright.sync_api import sync_playwright
        _wa_state["status"] = "waiting_qr"
        _wa_state["qr_png"] = None
        with sync_playwright() as pw:
            browser = pw.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR,
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                ignore_default_args=["--enable-automation"],
            )
            page = browser.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page.goto("https://web.whatsapp.com", timeout=60000)
            time.sleep(8)  # aguarda JS carregar

            # Espera QR aparecer ou já estar logado
            for _ in range(40):
                if page.query_selector('canvas, div[data-ref]'):
                    break
                if page.query_selector('div[aria-label="Lista de conversas"], div[data-testid="chat-list"]'):
                    _wa_state["status"] = "logged_in"
                    browser.close()
                    return
                time.sleep(3)

            # Tira screenshot só da área do QR
            qr_el = page.query_selector('div[data-ref] canvas, canvas[aria-label*="QR"], canvas[aria-label*="Scan"]')
            if qr_el:
                png = qr_el.screenshot()
            else:
                png = page.screenshot(full_page=False)
            _wa_state["qr_png"] = png
            _wa_state["status"] = "qr_ready"

            # Aguarda login (até 5 min)
            try:
                page.wait_for_selector('div[aria-label="Lista de conversas"]', timeout=300000)
                _wa_state["status"] = "logged_in"
            except Exception:
                _wa_state["status"] = "error"
            browser.close()
    except Exception as e:
        _wa_state["status"] = "error"
        _wa_state["qr_png"] = None


@app.route("/auth-whatsapp")
@login_required
def auth_whatsapp():
    return render_template("auth_whatsapp.html")


@app.route("/api/auth-whatsapp/start", methods=["POST"])
@login_required
def api_wa_start():
    if _wa_state["status"] in ("waiting_qr", "qr_ready"):
        return jsonify({"ok": True, "status": _wa_state["status"]})
    _wa_state["status"] = "idle"
    _wa_state["qr_png"] = None
    t = threading.Thread(target=_run_wa_auth, daemon=True)
    t.start()
    return jsonify({"ok": True, "status": "waiting_qr"})


@app.route("/api/auth-whatsapp/status")
@login_required
def api_wa_status():
    return jsonify({"status": _wa_state["status"], "has_qr": _wa_state["qr_png"] is not None})


@app.route("/api/auth-whatsapp/qr")
@login_required
def api_wa_qr():
    if not _wa_state["qr_png"]:
        return Response(status=204)
    return Response(_wa_state["qr_png"], mimetype="image/png")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
