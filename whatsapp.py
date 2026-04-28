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
        browser = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            args=["--no-sandbox"],
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
        # Clica no ícone de anexo
        anexo_btn = page.locator('[data-testid="attach-menu-plus"], [title="Anexar"]').first
        anexo_btn.wait_for(timeout=10000)
        anexo_btn.click()
        _delay()

        # Clica em "Fotos e vídeos"
        fotos_btn = page.locator('[data-testid="attach-image-input"], input[accept*="image"]').first
        fotos_btn.wait_for(timeout=5000)
        fotos_btn.set_input_files(imagem_path)
        _delay()

        # Aguarda preview aparecer
        page.wait_for_selector('[data-testid="media-caption-input-container"], div[contenteditable="true"][data-tab="11"]', timeout=10000)

        # Digita legenda no campo de caption
        caption = page.locator('[data-testid="media-caption-input-container"] div[contenteditable="true"], div[contenteditable="true"][data-tab="11"]').first
        caption.click()

        linhas = legenda.split("\n")
        for i, linha in enumerate(linhas):
            caption.type(linha, delay=20)
            if i < len(linhas) - 1:
                page.keyboard.press("Shift+Enter")

        _delay()
        page.keyboard.press("Enter")
        _delay()

        logger.info("Imagem com legenda enviada")

    except Exception as e:
        logger.warning(f"Falha ao enviar imagem, enviando só texto: {e}")
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
