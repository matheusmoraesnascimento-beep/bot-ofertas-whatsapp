import os
import time
import logging
import random
import tempfile
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

GROUP_NAME = os.getenv("WHATSAPP_GROUP_NAME", "")
SESSION_DIR = os.path.join(os.path.dirname(__file__), ".whatsapp_session")


def _delay():
    time.sleep(random.uniform(3, 7))


def _baixar_imagem(url: str) -> str | None:
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        ext = ".jpg"
        if "png" in resp.headers.get("Content-Type", ""):
            ext = ".png"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        tmp.write(resp.content)
        tmp.close()
        return tmp.name
    except Exception as e:
        logger.warning(f"Falha ao baixar imagem: {e}")
        return None


def enviar_para_grupo_whatsapp(mensagem: str, imagem_url: str = None):
    if not GROUP_NAME:
        logger.error("WhatsApp: WHATSAPP_GROUP_NAME não configurado")
        return False

    imagem_path = None
    if imagem_url:
        imagem_path = _baixar_imagem(imagem_url)

    with sync_playwright() as p:
        proxy_url = os.getenv("http_proxy") or os.getenv("HTTP_PROXY", "")
        proxy_cfg = None
        if proxy_url:
            from urllib.parse import urlparse
            p_parsed = urlparse(proxy_url)
            proxy_cfg = {
                "server": f"{p_parsed.scheme}://{p_parsed.hostname}:{p_parsed.port}",
                "username": p_parsed.username or "",
                "password": p_parsed.password or "",
            }

        browser = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            args=["--no-sandbox", "--start-minimized"],
            proxy=proxy_cfg,
        )
        page = browser.new_page()

        try:
            page.goto("https://web.whatsapp.com", timeout=60000)
            logger.info("WhatsApp Web aberto. Aguardando carregamento...")

            page.wait_for_selector('div[aria-label="Lista de conversas"]', timeout=90000)
            logger.info("WhatsApp Web carregado")

            _abrir_grupo(page, GROUP_NAME)

            if imagem_path and Path(imagem_path).exists():
                _enviar_imagem_com_legenda(page, imagem_path, mensagem)
            else:
                _enviar_mensagem(page, mensagem)

            logger.info(f"Mensagem enviada para grupo '{GROUP_NAME}'")
            _delay()
            return True

        except PlaywrightTimeout as e:
            logger.error(f"WhatsApp timeout: {e}")
            return False
        except Exception as e:
            logger.error(f"WhatsApp erro: {e}")
            return False
        finally:
            browser.close()
            if imagem_path:
                try:
                    os.unlink(imagem_path)
                except Exception:
                    pass


def _abrir_grupo(page, nome_grupo: str):
    try:
        resultado = page.locator(f'span[title="{nome_grupo}"]').first
        if resultado.count() > 0:
            resultado.click()
            _delay()
            logger.info(f"Grupo '{nome_grupo}' aberto por título")
            return

        caixa_busca = page.locator('[data-tab="3"][contenteditable="true"], [data-testid="chat-list-search"]').first
        caixa_busca.click()
        _delay()
        caixa_busca.fill(nome_grupo)
        _delay()

        resultado = page.locator(f'span[title="{nome_grupo}"]').first
        resultado.wait_for(timeout=15000)
        resultado.click()
        _delay()
        logger.info(f"Grupo '{nome_grupo}' aberto via busca")

    except Exception as e:
        raise RuntimeError(f"Não foi possível abrir grupo '{nome_grupo}': {e}")


def _enviar_imagem_com_legenda(page, imagem_path: str, legenda: str):
    try:
        # 1. Click Anexar
        page.locator('[aria-label="Anexar"]').first.click()
        time.sleep(1.5)

        # 2. Click "Fotos e vídeos" e intercepta file chooser
        with page.expect_file_chooser(timeout=10000) as fc_info:
            page.get_by_text("Fotos e vídeos", exact=False).first.click()
        fc = fc_info.value
        fc.set_files(imagem_path)
        time.sleep(4)

        # 3. Aguarda modal de preview e digita legenda
        # Campo de legenda = primeiro contenteditable sem data-tab="10"
        caption = page.locator('[contenteditable="true"]:not([data-tab="10"])').first
        caption.wait_for(timeout=10000)
        caption.click()

        linhas = legenda.split("\n")
        for i, linha in enumerate(linhas):
            caption.type(linha, delay=20)
            if i < len(linhas) - 1:
                page.keyboard.press("Shift+Enter")

        time.sleep(2)
        page.keyboard.press("Enter")
        _delay()
        logger.info("Imagem com legenda enviada")

    except Exception as e:
        logger.warning(f"Falha ao enviar imagem, enviando só texto: {e}")
        # Fecha modal se aberto
        try:
            page.keyboard.press("Escape")
            time.sleep(1)
            page.keyboard.press("Escape")
            time.sleep(1)
        except Exception:
            pass
        _enviar_mensagem(page, legenda)


def _enviar_mensagem(page, mensagem: str):
    try:
        caixa = page.locator('div[contenteditable="true"][data-tab="10"]')
        caixa.wait_for(timeout=10000)
        caixa.click()

        linhas = mensagem.split("\n")
        for i, linha in enumerate(linhas):
            caixa.type(linha, delay=30)
            if i < len(linhas) - 1:
                page.keyboard.press("Shift+Enter")

        _delay()
        page.keyboard.press("Enter")
        _delay()

    except Exception as e:
        raise RuntimeError(f"Erro ao enviar mensagem: {e}")
