import os
import sys
import threading
import base64
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from dotenv import load_dotenv

load_dotenv("config.env")

from db import init_db, listar_ofertas, buscar_url_destino, registrar_clique, listar_links_com_stats
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


CAMPOS_PUBLICOS = ["MIN_DESCONTO", "MAX_OFERTAS_POR_RODADA",
                   "INTERVALO_ENTRE_POSTS", "RODAR_A_CADA_MINUTOS",
                   "HORA_INICIO", "HORA_FIM", "WHATSAPP_GROUP_NAME", "FONTES_ATIVAS"]


@app.route("/api/config", methods=["GET", "POST"])
@login_required
def api_config():
    config_file = "config.env"
    if request.method == "GET":
        cfg = {k: os.getenv(k, "") for k in CAMPOS_PUBLICOS}
        if os.path.exists(config_file):
            with open(config_file) as f:
                for linha in f:
                    linha = linha.strip()
                    if "=" in linha and not linha.startswith("#"):
                        k, v = linha.split("=", 1)
                        if k.strip() in CAMPOS_PUBLICOS:
                            cfg[k.strip()] = v.strip()
        return jsonify(cfg)
    data = request.json or {}
    for k, v in data.items():
        os.environ[k] = str(v)
    linhas = []
    if os.path.exists(config_file):
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


@app.route("/api/fontes", methods=["POST"])
@login_required
def api_fontes():
    data = request.json or {}
    fontes = data.get("fontes", "amazon,ml")
    os.environ["FONTES_ATIVAS"] = fontes
    config_file = "config.env"
    linhas = []
    if os.path.exists(config_file):
        with open(config_file) as f:
            linhas = f.readlines()
    found = False
    for i, linha in enumerate(linhas):
        if linha.strip().startswith("FONTES_ATIVAS="):
            linhas[i] = f"FONTES_ATIVAS={fontes}\n"
            found = True
            break
    if not found:
        linhas.append(f"FONTES_ATIVAS={fontes}\n")
    with open(config_file, "w") as f:
        f.writelines(linhas)
    return jsonify({"ok": True, "fontes": fontes})


# --- WhatsApp Auth ---
_wa_state = {"status": "idle", "qr_png": None, "page_ref": None}  # idle | waiting_qr | qr_ready | logged_in | error


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


@app.route("/r/<slug>")
def redirect_link(slug):
    url = buscar_url_destino(slug)
    if not url:
        return "Link não encontrado", 404
    registrar_clique(slug)
    return redirect(url, code=302)


@app.route("/api/links")
@login_required
def api_links():
    return jsonify(listar_links_com_stats())


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@app.route("/instagram-posts")
@login_required
def instagram_posts():
    hoje = datetime.now().strftime("%Y-%m-%d")
    pasta = os.path.join(_ROOT, "posts", hoje)
    posts = []
    if os.path.isdir(pasta):
        for i in range(1, 4):
            img_path = os.path.join(pasta, f"post_{i}.jpg")
            txt_path = os.path.join(pasta, f"post_{i}.txt")
            if os.path.exists(img_path):
                caption = open(txt_path, encoding="utf-8").read() if os.path.exists(txt_path) else ""
                posts.append({"indice": i, "caption": caption, "data": hoje})

    reels = []
    pasta_reels = os.path.join(_ROOT, "posts", hoje, "reels")
    if os.path.isdir(pasta_reels):
        for i in range(1, 4):
            img_path = os.path.join(pasta_reels, f"reel_{i}.jpg")
            txt_path = os.path.join(pasta_reels, f"reel_{i}.txt")
            mp4_path = os.path.join(pasta_reels, f"reel_{i}.mp4")
            if os.path.exists(img_path):
                caption = open(txt_path, encoding="utf-8").read() if os.path.exists(txt_path) else ""
                reels.append({"indice": i, "caption": caption, "data": hoje,
                               "tem_video": os.path.exists(mp4_path)})

    return render_template("instagram_posts.html", posts=posts, reels=reels, hoje=hoje)


@app.route("/api/instagram-posts/imagem/<data>/<filename>")
@login_required
def instagram_post_imagem(data, filename):
    import re
    from flask import send_from_directory
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", data):
        return "invalid", 400
    if not re.match(r"^post_[123]\.jpg$", filename):
        return "invalid", 400
    pasta = os.path.join(_ROOT, "posts", data)
    return send_from_directory(pasta, filename)


@app.route("/api/instagram-posts/reels/<data>/<filename>")
@login_required
def instagram_reel_arquivo(data, filename):
    import re
    from flask import send_from_directory
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", data):
        return "invalid", 400
    if not re.match(r"^reel_[123]\.(jpg|mp4)$", filename):
        return "invalid", 400
    pasta = os.path.join(_ROOT, "posts", data, "reels")
    return send_from_directory(pasta, filename)


@app.route("/api/instagram-posts/gerar", methods=["POST"])
@login_required
def api_gerar_posts_instagram():
    try:
        import sys
        sys.path.insert(0, _ROOT)
        from amazon import buscar_ofertas_amazon
        from mercadolivre import buscar_ofertas_mercadolivre
        from filtros import filtrar_melhores_ofertas
        from instagram_posts import _gerar_imagem, _gerar_caption, POSTS_DIR

        categorias = ["air fryer", "fone bluetooth", "smartwatch", "secador de cabelo", "robo aspirador"]
        ofertas = []
        for cat in categorias:
            try:
                ofertas += buscar_ofertas_amazon(cat)
            except Exception:
                pass
            try:
                ofertas += buscar_ofertas_mercadolivre(cat)
            except Exception:
                pass

        filtradas = filtrar_melhores_ofertas(ofertas, 15)
        filtradas.sort(key=lambda o: o.get("desconto_percentual", 0), reverse=True)

        selecionadas = []
        vistos = set()
        for o in filtradas:
            chave = o["produto"][:40]
            if chave not in vistos:
                selecionadas.append(o)
                vistos.add(chave)
            if len(selecionadas) >= 3:
                break

        if not selecionadas:
            return jsonify({"ok": False, "erro": "Nenhuma oferta encontrada"}), 200

        hoje = datetime.now().strftime("%Y-%m-%d")
        pasta = os.path.join(_ROOT, "posts", hoje)
        os.makedirs(pasta, exist_ok=True)

        gerados = []
        for i, o in enumerate(selecionadas, start=1):
            oferta_fmt = {
                "produto": o["produto"],
                "loja": o["loja"],
                "preco": o["preco_atual"],
                "desconto": o.get("desconto_percentual", 0),
                "imagem": o.get("imagem", ""),
                "link": o.get("link_afiliado", ""),
            }
            img = _gerar_imagem(oferta_fmt, i - 1)
            img.save(os.path.join(pasta, f"post_{i}.jpg"), "JPEG", quality=92)
            caption = _gerar_caption(oferta_fmt)
            with open(os.path.join(pasta, f"post_{i}.txt"), "w", encoding="utf-8") as f:
                f.write(caption)
            gerados.append(o["produto"][:50])

        return jsonify({"ok": True, "gerados": len(gerados), "produtos": gerados})
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500


@app.route("/api/instagram-posts/gerar-reels", methods=["POST"])
@login_required
def api_gerar_reels_instagram():
    try:
        import sys
        sys.path.insert(0, _ROOT)
        from amazon import buscar_ofertas_amazon
        from mercadolivre import buscar_ofertas_mercadolivre
        from filtros import filtrar_melhores_ofertas
        from db import salvar_oferta
        from instagram_posts import _gerar_imagem_reels, _gerar_caption, _imagem_para_video, REELS_W, REELS_H

        categorias = ["air fryer", "fone bluetooth", "smartwatch", "secador de cabelo", "robo aspirador"]
        ofertas = []
        for cat in categorias:
            try:
                ofertas += buscar_ofertas_amazon(cat)
            except Exception:
                pass
            try:
                ofertas += buscar_ofertas_mercadolivre(cat)
            except Exception:
                pass

        filtradas = filtrar_melhores_ofertas(ofertas, 15)
        filtradas.sort(key=lambda o: o.get("desconto_percentual", 0), reverse=True)

        selecionadas = []
        vistos = set()
        for o in filtradas:
            chave = o["produto"][:40]
            if chave not in vistos:
                selecionadas.append(o)
                vistos.add(chave)
            if len(selecionadas) >= 3:
                break

        if not selecionadas:
            return jsonify({"ok": False, "erro": "Nenhuma oferta encontrada"}), 200

        hoje = datetime.now().strftime("%Y-%m-%d")
        pasta = os.path.join(_ROOT, "posts", hoje, "reels")
        os.makedirs(pasta, exist_ok=True)

        gerados = []
        for i, o in enumerate(selecionadas, start=1):
            oferta_fmt = {
                "produto": o["produto"],
                "loja": o["loja"],
                "preco": o["preco_atual"],
                "desconto": o.get("desconto_percentual", 0),
                "imagem": o.get("imagem", ""),
                "link": o.get("link_afiliado", ""),
            }
            from pathlib import Path as _Path
            img = _gerar_imagem_reels(oferta_fmt, i - 1)
            img_path = _Path(pasta) / f"reel_{i}.jpg"
            img.save(str(img_path), "JPEG", quality=92)
            video_path = _Path(pasta) / f"reel_{i}.mp4"
            _imagem_para_video(img_path, video_path)
            caption = _gerar_caption(oferta_fmt)
            with open(os.path.join(pasta, f"reel_{i}.txt"), "w", encoding="utf-8") as f:
                f.write(caption)
            gerados.append(o["produto"][:50])

        return jsonify({"ok": True, "gerados": len(gerados), "produtos": gerados})
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
