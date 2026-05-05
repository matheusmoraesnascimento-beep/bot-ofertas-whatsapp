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
CHANNEL_NAME = os.getenv("WHATSAPP_CHANNEL_NAME", "")
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
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
            ignore_default_args=["--enable-automation"],
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            proxy=proxy_cfg,
        )
        page = browser.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

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

            if CHANNEL_NAME:
                try:
                    _abrir_canal(page, CHANNEL_NAME)
                    if imagem_path and Path(imagem_path).exists():
                        _enviar_imagem_com_legenda(page, imagem_path, mensagem)
                    else:
                        _enviar_mensagem(page, mensagem)
                    logger.info(f"Mensagem enviada para canal '{CHANNEL_NAME}'")
                    _delay()
                except Exception as e:
                    logger.warning(f"Canal falhou (grupo ok): {e}")

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


def _abrir_canal(page, nome_canal: str):
    try:
        tab = page.locator('[data-tab="5"], [aria-label*="tualiza"], [aria-label*="Channel"], [aria-label*="Canais"]').first
        tab.wait_for(state="visible", timeout=10000)
        tab.click()
        _delay()

        locator = page.locator(f'span[title="{nome_canal}"]')
        if locator.count() == 0:
            caixa = page.locator('[data-tab="6"][contenteditable="true"], [data-testid="chat-list-search"]').first
            caixa.click()
            _delay()
            caixa.fill(nome_canal)
            _delay()
            locator = page.locator(f'span[title="{nome_canal}"]')
            locator.first.wait_for(timeout=15000)

        locator.first.click()
        _delay()
        logger.info(f"Canal '{nome_canal}' aberto")
    except Exception as e:
        raise RuntimeError(f"Não foi possível abrir canal '{nome_canal}': {e}")


def _enviar_imagem_com_legenda(page, imagem_path: str, legenda: str) -> None:
    CAPTION_SELECTORS = [
        '[contenteditable="true"][data-tab="6"]',
        'div[role="textbox"][aria-label*="egenda"]',
        'div[role="textbox"][aria-placeholder*="egenda"]',
        '[contenteditable="true"]:not([data-tab="10"])',
    ]

    for tentativa in range(3):
        try:
            page.locator('[aria-label="Anexar"]').first.click()
            time.sleep(2)

            with page.expect_file_chooser(timeout=12000) as fc_info:
                page.get_by_text("Fotos e vídeos", exact=False).first.click()
            fc_info.value.set_files(imagem_path)
            time.sleep(5)

            caption = None
            for sel in CAPTION_SELECTORS:
                try:
                    el = page.locator(sel).first
                    el.wait_for(state="visible", timeout=5000)
                    caption = el
                    break
                except Exception as sel_err:
                    logger.debug(f"Seletor {sel!r} falhou: {sel_err}")
                    continue

            if caption is None:
                raise RuntimeError(f"caption field not found (tried {len(CAPTION_SELECTORS)} selectors)")

            caption.click()
            linhas = legenda.split("\n")
            for i, linha in enumerate(linhas):
                caption.type(linha, delay=20)
                if i < len(linhas) - 1:
                    page.keyboard.press("Shift+Enter")

            time.sleep(2)
            page.keyboard.press("Enter")
            _delay()
            logger.info(f"Imagem enviada (tentativa {tentativa + 1})")
            return

        except Exception as e:
            logger.warning(f"Tentativa {tentativa + 1}/3 falhou: {e}")
            try:
                page.keyboard.press("Escape")
                time.sleep(1.5)
                page.keyboard.press("Escape")
                time.sleep(1.5)
            except Exception:
                pass

    logger.warning("Todas tentativas falharam — enviando texto simples")
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
